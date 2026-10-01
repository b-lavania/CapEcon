"""pypricing fit wrapper — lazy import, cache summaries on workspace.meta."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from analytics.demand_panel import build_demand_panel, panel_power
from core.workspace import Workspace


def pypricing_available() -> bool:
    try:
        import pypricing  # noqa: F401
        return True
    except ImportError:
        return False


def _claim_type(workspace: Workspace) -> str:
    src = (workspace.meta or {}).get("data_source", "synthetic")
    return "simulated" if src in ("synthetic", None, "") else "associational"


def _floor_for_sku(workspace: Workspace, sku: str, profile: dict[str, Any]) -> float | None:
    from analytics.decisions import price_exceptions
    from ontology.decision_rules import load_rules_for_vertical

    vertical = profile.get("ontology_vertical", "capability_lifecycle")
    semantics = load_rules_for_vertical(vertical)
    econ = price_exceptions([], profile, semantics=semantics, workspace=workspace, capability_id=sku)
    floor = econ.get("floor_usd")
    return float(floor) if floor is not None else None


def surplus_optimal_price(
    model: Any,
    sku: str,
    floor_usd: float,
    panel: pd.DataFrame,
    *,
    hdi_prob: float = 0.9,
) -> tuple[float | None, float | None]:
    """Grid search max (p - floor) * E[Q]. Returns (surplus_opt, revenue_opt diagnostic)."""
    sub = panel[panel["sku"].astype(str) == str(sku)]
    if sub.empty:
        return None, None
    p_min = max(float(sub["price"].min()) * 0.8, floor_usd)
    p_max = float(sub["price"].max()) * 1.3
    if p_max <= p_min:
        p_max = p_min * 1.5
    grid = np.linspace(p_min, p_max, 25)

    control_cols = [c for c in panel.columns if c.startswith("control_")]
    controls: dict[str, float] = {}
    if control_cols:
        for col in control_cols:
            controls[col] = float(sub[col].median())

    best_surplus = -np.inf
    best_p: float | None = None
    rows = []
    for p in grid:
        row = {"sku": sku, "price": float(p), **controls}
        pred = model.predict(pd.DataFrame([row]), hdi_prob=hdi_prob)
        q = float(pred["quantity_mean"].iloc[0])
        surplus = (float(p) - floor_usd) * q
        rows.append((float(p), q, surplus))
        if surplus > best_surplus:
            best_surplus = surplus
            best_p = float(p)

    revenue_opt: float | None = None
    try:
        bounds = {sku: (p_min, p_max)}
        controls_df = pd.DataFrame([{"sku": sku, **controls}]) if controls else None
        opt = model.optimize_prices(price_bounds=bounds, controls_df=controls_df)
        if opt is not None and not opt.empty:
            revenue_opt = float(opt.loc[opt["sku"].astype(str) == str(sku), "optimal_price"].iloc[0])
    except Exception:
        revenue_opt = None

    if best_p is None or best_surplus <= 0:
        return None, revenue_opt
    return round(best_p, 4), revenue_opt


def fit_demand(
    workspace: Workspace,
    panel: pd.DataFrame | None = None,
    *,
    draws: int = 300,
    tune: int = 300,
    chains: int = 2,
    seed: int = 42,
    floors: dict[str, float] | None = None,
) -> dict[str, Any] | None:
    """Fit LogLogDemandModel; return JSON-safe summary dict."""
    if not pypricing_available():
        return None

    from pypricing import LogLogDemandModel, PanelColumns

    panel = panel if panel is not None else build_demand_panel(workspace)
    power = panel_power(panel)
    if not power["ok"]:
        return {"underpowered": True, "reasons": power["reasons"], "claim_type": _claim_type(workspace)}

    profile = workspace.profile
    floors = floors or {}
    fit_df = panel[["sku", "period", "price", "quantity"]].copy()
    control_cols = [c for c in panel.columns if c.startswith("control_")]
    for col in control_cols:
        fit_df[col] = panel[col]

    kwargs: dict[str, Any] = {}
    if "category_1" in panel.columns and panel["category_1"].nunique() >= 2:
        fit_df["category_1"] = panel["category_1"]
        kwargs["panel_columns"] = PanelColumns(group_columns=("category_1",))

    model = LogLogDemandModel(**kwargs)
    model.fit(fit_df, draws=draws, tune=tune, chains=chains, random_seed=seed, cores=1, progressbar=False)

    summary = model.fit_summary()
    sku_summaries: dict[str, Any] = {}
    for sku in sorted(panel["sku"].unique()):
        sku = str(sku)
        row = summary[summary.index.astype(str) == sku] if sku in summary.index.astype(str) else None
        elasticity_mean = None
        elasticity_hdi: list[float] = []
        if row is not None and not row.empty and "elasticity" in row.columns:
            elasticity_mean = float(row["elasticity"].iloc[0])
        try:
            post = model.quantity_multiplier_summary(price_multiplier=1.10, hdi_prob=0.9)
            sku_row = post[post["sku"].astype(str) == sku]
            qty_mult = float(sku_row["quantity_multiplier_mean"].iloc[0]) if not sku_row.empty else None
        except Exception:
            qty_mult = None

        floor = floors.get(sku)
        if floor is None:
            floor = _floor_for_sku(workspace, sku, profile)
        surplus_opt = revenue_opt = None
        if floor is not None:
            surplus_opt, revenue_opt = surplus_optimal_price(model, sku, floor, panel)

        sku_summaries[sku] = {
            "elasticity_mean": round(elasticity_mean, 4) if elasticity_mean is not None else None,
            "elasticity_hdi": elasticity_hdi,
            "surplus_opt_usd": surplus_opt,
            "revenue_opt_usd": round(revenue_opt, 4) if revenue_opt is not None else None,
            "qty_mult_1p10_mean": round(qty_mult, 4) if qty_mult is not None else None,
        }

    return {
        "underpowered": False,
        "claim_type": _claim_type(workspace),
        "model": "log_log",
        "n_skus": int(panel["sku"].nunique()),
        "n_periods": int(panel["period"].nunique()),
        "skus": sku_summaries,
    }


def fit_and_cache_demand(workspace: Workspace, **kwargs: Any) -> dict[str, Any] | None:
    """Fit and write summary to workspace.meta['demand_fit']."""
    result = fit_demand(workspace, **kwargs)
    if result is not None:
        workspace.meta = dict(workspace.meta or {})
        workspace.meta["demand_fit"] = result
    return result


def get_demand_fit(workspace: Workspace | None) -> dict[str, Any] | None:
    if workspace is None:
        return None
    return (workspace.meta or {}).get("demand_fit")


def enrich_economics_from_demand_fit(
    economics: dict[str, Any],
    workspace: Workspace | None,
    capability_id: str | None,
) -> dict[str, Any]:
    """Attach cached surplus_opt from meta — no MCMC."""
    out = dict(economics)
    if workspace is None or not capability_id:
        return out
    fit = get_demand_fit(workspace)
    if not fit or fit.get("underpowered"):
        return out
    sku = (fit.get("skus") or {}).get(str(capability_id))
    if not sku:
        return out
    if sku.get("surplus_opt_usd") is not None:
        out["surplus_opt_usd"] = sku["surplus_opt_usd"]
    if sku.get("elasticity_mean") is not None:
        out["demand_elasticity_mean"] = sku["elasticity_mean"]
    return out


def demand_caption_for_capability(workspace: Workspace | None, capability_id: str | None) -> str:
    """One-line caption for Decision Card when cache hit."""
    fit = get_demand_fit(workspace)
    if not fit or fit.get("underpowered") or not capability_id:
        return ""
    sku = fit.get("skus", {}).get(str(capability_id))
    if not sku:
        return ""
    eps = sku.get("elasticity_mean")
    surplus = sku.get("surplus_opt_usd")
    parts: list[str] = []
    if eps is not None:
        hdi = sku.get("elasticity_hdi") or []
        if len(hdi) == 2:
            parts.append(f"ε {eps:.2f} [{hdi[0]:.2f}, {hdi[1]:.2f}]")
        else:
            parts.append(f"ε {eps:.2f}")
    if surplus is not None:
        parts.append(f"surplus-opt list ${surplus:.2f}")
    return "; ".join(parts)


def estimate_heterogeneous_elasticity(
    panel: pd.DataFrame,
    feature_cols: list[str] | None = None,
    *,
    min_samples: int = 150,
) -> dict[str, Any]:
    """
    Causal Forest DML estimate of heterogeneous price elasticity.
    Falls back to OLS log-log when econml not installed or underpowered.

    Args:
        panel: build_demand_panel() output — columns sku, price, quantity, [control_*]
        feature_cols: subset of control_* columns to use as heterogeneity moderators
        min_samples: minimum rows for CausalForestDML; below this → OLS fallback

    Returns dict with:
        elasticity_mean, elasticity_std, method, claim_type, underpowered, skus
    """
    if panel.empty or "price" not in panel.columns or "quantity" not in panel.columns:
        return {"elasticity_mean": None, "underpowered": True, "claim_type": "simulated", "method": "none"}

    n = len(panel)
    underpowered = n < min_samples

    if not underpowered:
        try:
            from econml.dml import CausalForestDML

            T = np.log(panel["price"].values.reshape(-1, 1))
            Y = np.log(panel["quantity"].clip(lower=1).values)
            X_cols = [c for c in (feature_cols or []) if c in panel.columns]
            X = panel[X_cols].fillna(0).values if X_cols else np.ones((n, 1))
            model = CausalForestDML(n_estimators=100, random_state=42)
            model.fit(Y, T.ravel(), X=X)
            effects = model.effect(X)
            return {
                "elasticity_mean": round(float(np.mean(effects)), 4),
                "elasticity_std": round(float(np.std(effects)), 4),
                "method": "CausalForestDML",
                "claim_type": "associational",
                "underpowered": False,
                "skus": {},
            }
        except ImportError:
            pass

    import warnings

    log_p = np.log(panel["price"].clip(lower=1e-6).values)
    log_q = np.log(panel["quantity"].clip(lower=1).values)
    if np.std(log_p) < 1e-6:
        return {
            "elasticity_mean": None,
            "underpowered": True,
            "claim_type": "simulated",
            "method": "ols_fallback",
            "message": "No price variation",
        }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        slope = float(np.cov(log_p, log_q)[0, 1] / np.var(log_p))
    return {
        "elasticity_mean": round(slope, 4),
        "elasticity_std": None,
        "method": "ols_log_log_fallback",
        "claim_type": "simulated",
        "underpowered": underpowered,
    }

