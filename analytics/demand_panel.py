"""Build SKU-week price/quantity panels for pypricing."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from analytics.price_block import pricing_mode_for_profile
from core.workspace import Workspace

MIN_SKUS = 4
MIN_PERIODS = 8
MIN_ROWS = 40
MIN_PRICE_CV_SKUS = 2


def _iso_week(ts: pd.Series) -> pd.Series:
    return pd.to_datetime(ts).dt.strftime("%G-W%V")


def build_demand_panel(workspace: Workspace) -> pd.DataFrame:
    """Roll verified outcomes into pypricing panel columns."""
    outcomes = getattr(workspace, "outcomes", pd.DataFrame())
    runs = getattr(workspace, "runs", pd.DataFrame())
    caps = getattr(workspace, "capabilities", pd.DataFrame())
    if outcomes is None or outcomes.empty or runs is None or runs.empty:
        return pd.DataFrame(columns=["sku", "period", "period_ord", "price", "quantity"])

    verified = outcomes.copy()
    if "verified" in verified.columns and "success" in verified.columns:
        verified = verified[verified["verified"].astype(bool) & verified["success"].astype(bool)]
    elif "verified" in verified.columns:
        verified = verified[verified["verified"].astype(bool)]
    if verified.empty:
        return pd.DataFrame(columns=["sku", "period", "period_ord", "price", "quantity"])

    run_cols = ["run_id", "capability_id"]
    if "tokens_in" in runs.columns:
        run_cols.append("tokens_in")
    merged = verified.merge(
        runs[run_cols],
        left_on="agent_run_id",
        right_on="run_id",
        how="inner",
    )
    if merged.empty or "capability_id" not in merged.columns:
        return pd.DataFrame(columns=["sku", "period", "period_ord", "price", "quantity"])

    merged["occurred_at"] = pd.to_datetime(merged["occurred_at"])
    merged["period"] = _iso_week(merged["occurred_at"])
    merged["sku"] = merged["capability_id"].astype(str)

    if "list_price_per_outcome_usd" in merged.columns:
        merged["price"] = pd.to_numeric(merged["list_price_per_outcome_usd"], errors="coerce")
    else:
        merged["price"] = np.nan

    if merged["price"].isna().all():
        subs = getattr(workspace, "subscriptions", pd.DataFrame())
        fallback = float(workspace.profile.get("priors", {}).get("policy_cpso_cap", 0.99) or 0.99)
        if subs is not None and not subs.empty and "list_price_per_outcome_usd" in subs.columns:
            acct_list = subs.set_index("account_id")["list_price_per_outcome_usd"].to_dict()
            merged["price"] = merged["account_id"].astype(str).map(acct_list)
        merged["price"] = merged["price"].fillna(fallback)

    mode = pricing_mode_for_profile(workspace.profile)
    if mode == "marketplace_take" and "base_list_usd" in (caps.columns if not caps.empty else []):
        cap_list = caps.set_index("capability_id")["base_list_usd"].to_dict()
        take = float(workspace.profile.get("priors", {}).get("marketplace_take_rate", 0.12) or 0.12)
        merged["price"] = merged["sku"].map(lambda s: float(cap_list.get(s, 0.99) or 0.99) * take)

    merged = merged[merged["price"] > 0]
    if merged.empty:
        return pd.DataFrame(columns=["sku", "period", "period_ord", "price", "quantity"])

    if not caps.empty and "agent_id" in caps.columns:
        agent_map = caps.set_index("capability_id")["agent_id"].astype(str).to_dict()
        merged["category_1"] = merged["sku"].map(agent_map)
    else:
        merged["category_1"] = "default"

    agg: dict[str, Any] = {
        "quantity": ("outcome_id", "count"),
        "price": ("price", "median"),
    }
    if "tokens_in" in merged.columns:
        agg["control_tokens"] = ("tokens_in", "mean")

    panel = merged.groupby(["sku", "period"], as_index=False).agg(**agg)
    periods = sorted(panel["period"].unique())
    period_ord = {p: i for i, p in enumerate(periods)}
    panel["period_ord"] = panel["period"].map(period_ord)
    panel["quantity"] = panel["quantity"].astype(int)
    panel["price"] = panel["price"].astype(float).round(4)
    if "control_tokens" in panel.columns:
        panel["control_tokens"] = panel["control_tokens"].fillna(0).astype(float)
    return panel


def panel_power(panel: pd.DataFrame) -> dict[str, Any]:
    """Return {ok, reasons} for whether a panel is fit-ready."""
    reasons: list[str] = []
    if panel is None or panel.empty:
        return {"ok": False, "reasons": ["panel empty"], "n_skus": 0, "n_periods": 0, "n_rows": 0}

    n_skus = int(panel["sku"].nunique())
    n_periods = int(panel["period"].nunique())
    n_rows = int(len(panel))
    if n_skus < MIN_SKUS:
        reasons.append(f"skus {n_skus} < {MIN_SKUS}")
    if n_periods < MIN_PERIODS:
        reasons.append(f"periods {n_periods} < {MIN_PERIODS}")
    if n_rows < MIN_ROWS:
        reasons.append(f"rows {n_rows} < {MIN_ROWS}")

    cv_skus = 0
    for _, grp in panel.groupby("sku"):
        prices = grp["price"].astype(float)
        if len(prices) >= 2 and prices.std() > 0 and prices.mean() > 0:
            cv_skus += 1
    if cv_skus < MIN_PRICE_CV_SKUS:
        reasons.append(f"price CV skus {cv_skus} < {MIN_PRICE_CV_SKUS}")

    return {
        "ok": not reasons,
        "reasons": reasons,
        "n_skus": n_skus,
        "n_periods": n_periods,
        "n_rows": n_rows,
        "price_cv_skus": cv_skus,
    }
