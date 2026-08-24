"""Price block for GrowthDecisionRecords.

Ranking metric (Radar sort / existing headline) stays `primary_metric_usd`.
Unit cost of producing one verified outcome lives in `floor_usd`.
Expected harm is `risk_usd` and never sits inside the floor.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from core.workspace import Workspace

PRICING_MODES = ("internal_budget", "product_sku", "marketplace_take")
COST_BASIS_RANK = {
    "simulated": 0,
    "estimated": 1,
    "allocated": 2,
    "metered": 3,
}

_INTERNAL_PRESETS = frozenset(
    {"assistant_heavy", "workspace_crm", "ops_mission", "openmed_v22"}
)
_MARKETPLACE_PRESETS = frozenset({"marketplace_agentic"})
_SKU_PRESETS = frozenset({"api_metered"})


def primary_metric_label(
    semantics: dict[str, Any] | None,
    default: str = "cost_of_leaving_live_usd",
) -> str:
    """Read the YAML metric key from dotted or nested form."""
    if not semantics:
        return default
    nested = semantics.get("economics")
    if isinstance(nested, dict) and nested.get("primary_metric_label"):
        return str(nested["primary_metric_label"])
    dotted = semantics.get("economics.primary_metric_label")
    if dotted:
        return str(dotted)
    return default


def primary_metric_display(semantics: dict[str, Any] | None) -> str | None:
    if not semantics:
        return None
    nested = semantics.get("economics")
    if isinstance(nested, dict) and nested.get("primary_metric_display"):
        return str(nested["primary_metric_display"])
    dotted = semantics.get("economics.primary_metric_display")
    if dotted:
        return str(dotted)
    return None


def humanize_metric_label(key: str | None, display: str | None = None) -> str:
    if display:
        return display
    if not key:
        return "Cost of leaving live"
    stem = key[:-4] if key.endswith("_usd") else key
    return stem.replace("_", " ").strip().capitalize()


def display_metric_label(economics: dict[str, Any]) -> str:
    return humanize_metric_label(
        economics.get("primary_metric_label"),
        economics.get("primary_metric_display"),
    )


def pricing_mode_for_profile(profile: dict[str, Any] | None) -> str:
    profile = profile or {}
    explicit = profile.get("pricing_mode")
    if explicit in PRICING_MODES:
        return explicit
    preset = profile.get("preset_id")
    vertical = profile.get("ontology_vertical")
    billing = profile.get("billing_model")
    if preset in _MARKETPLACE_PRESETS or vertical == "marketplace_commerce":
        return "marketplace_take"
    if preset in _SKU_PRESETS:
        return "product_sku"
    if preset in _INTERNAL_PRESETS or vertical == "clinical_runtime":
        return "internal_budget"
    if billing == "usage_based":
        return "product_sku"
    return "internal_budget"


def weakest_cost_basis(bases: list[str]) -> str:
    present = [b for b in bases if b in COST_BASIS_RANK]
    if not present:
        return "simulated"
    return min(present, key=lambda b: COST_BASIS_RANK[b])


def cost_basis_for_workspace(workspace: Workspace | None) -> str:
    if workspace is None:
        return "simulated"
    src = (workspace.meta or {}).get("data_source", "synthetic")
    if src in ("synthetic", None, ""):
        return "simulated"
    usage = getattr(workspace, "usage_events", pd.DataFrame())
    if usage is not None and not usage.empty and "cost_usd" in usage.columns:
        return "estimated"
    return "estimated"


def _n_verified(
    workspace: Workspace | None,
    *,
    capability_id: str | None = None,
    account_id: str | None = None,
    run_ids: set[str] | None = None,
) -> int:
    if workspace is None:
        return 0
    outcomes = getattr(workspace, "outcomes", pd.DataFrame())
    runs = getattr(workspace, "runs", pd.DataFrame())
    if run_ids is None and runs is not None and not runs.empty:
        scoped = runs
        if capability_id and "capability_id" in scoped.columns:
            scoped = scoped[scoped["capability_id"].astype(str) == str(capability_id)]
        if account_id and "workspace_id" in getattr(workspace, "seats", pd.DataFrame()).columns:
            seats = workspace.seats
            seat_ids = set(seats.loc[seats["workspace_id"] == account_id, "seat_id"].astype(str))
            if "seat_id" in scoped.columns:
                scoped = scoped[scoped["seat_id"].astype(str).isin(seat_ids)]
        run_ids = set(scoped["run_id"].astype(str)) if "run_id" in scoped.columns else set()
    if outcomes is None or outcomes.empty:
        if runs is None or runs.empty:
            return 0
        scoped = runs
        if capability_id and "capability_id" in scoped.columns:
            scoped = scoped[scoped["capability_id"].astype(str) == str(capability_id)]
        if "success" in scoped.columns:
            return int(scoped["success"].astype(bool).sum())
        return 0
    verified = outcomes
    if "verified" in verified.columns and "success" in verified.columns:
        verified = verified[verified["verified"].astype(bool) & verified["success"].astype(bool)]
    elif "verified" in verified.columns:
        verified = verified[verified["verified"].astype(bool)]
    if run_ids is not None and "agent_run_id" in verified.columns:
        verified = verified[verified["agent_run_id"].astype(str).isin(run_ids)]
    return int(len(verified))


def _scoped_runs(
    workspace: Workspace | None,
    *,
    capability_id: str | None = None,
    account_id: str | None = None,
) -> pd.DataFrame:
    empty = pd.DataFrame()
    if workspace is None:
        return empty
    runs = getattr(workspace, "runs", empty)
    if runs is None or runs.empty:
        return empty
    scoped = runs
    if capability_id and "capability_id" in scoped.columns:
        scoped = scoped[scoped["capability_id"].astype(str) == str(capability_id)]
    if account_id:
        seats = getattr(workspace, "seats", empty)
        if seats is not None and not seats.empty and "workspace_id" in seats.columns:
            seat_ids = set(seats.loc[seats["workspace_id"] == account_id, "seat_id"].astype(str))
            if "seat_id" in scoped.columns:
                scoped = scoped[scoped["seat_id"].astype(str).isin(seat_ids)]
    return scoped


def _hitl_usd(
    workspace: Workspace | None,
    runs: pd.DataFrame,
    profile: dict[str, Any],
) -> float:
    if workspace is None:
        return 0.0
    approvals = getattr(workspace, "approvals", pd.DataFrame())
    if approvals is None or approvals.empty:
        return 0.0
    priors = profile.get("priors", {})
    hourly = float(priors.get("reviewer_loaded_hourly_usd", 0) or 0)
    minutes = float(priors.get("review_minutes_per_approval", 4.0) or 4.0)
    if hourly <= 0:
        return 0.0
    appr = approvals
    if not runs.empty and "run_id" in appr.columns and "run_id" in runs.columns:
        appr = appr[appr["run_id"].astype(str).isin(set(runs["run_id"].astype(str)))]
    if "review_minutes" in appr.columns:
        total_min = float(appr["review_minutes"].fillna(0).sum())
    else:
        total_min = float(len(appr) * minutes)
    return total_min / 60.0 * hourly


def _implied_list_usd(
    workspace: Workspace | None,
    profile: dict[str, Any],
    runs: pd.DataFrame,
    n_verified: int,
) -> float | None:
    if n_verified <= 0 or workspace is None:
        return None
    subs = getattr(workspace, "subscriptions", pd.DataFrame())
    all_runs = getattr(workspace, "runs", pd.DataFrame())
    share = 1.0
    if all_runs is not None and not all_runs.empty and not runs.empty:
        share = len(runs) / max(len(all_runs), 1)
    if subs is not None and not subs.empty and "mrr_usd" in subs.columns:
        mrr = float(subs["mrr_usd"].fillna(0).sum())
        if mrr > 0:
            return round(mrr * share / n_verified, 4)
    priors = profile.get("priors", {})
    rpt = float(priors.get("revenue_per_1k_tokens", 0) or 0)
    if rpt > 0 and not runs.empty:
        tin = float(runs["tokens_in"].fillna(0).sum()) if "tokens_in" in runs.columns else 0.0
        tout = float(runs["tokens_out"].fillna(0).sum()) if "tokens_out" in runs.columns else 0.0
        return round(((tin + tout) / 1000.0 * rpt) / n_verified, 4)
    return None


def _marketplace_take_usd(
    workspace: Workspace | None,
    *,
    capability_id: str | None,
    n_verified: int,
) -> float | None:
    if workspace is None or n_verified <= 0:
        return None
    tx = getattr(workspace, "agent_transactions", pd.DataFrame())
    if tx is None or tx.empty or "platform_revenue_usd" not in tx.columns:
        return None
    scoped = tx
    if capability_id and "capability_id" in scoped.columns:
        scoped = scoped[scoped["capability_id"].astype(str) == str(capability_id)]
    if scoped.empty:
        return None
    return round(float(scoped["platform_revenue_usd"].fillna(0).sum()) / n_verified, 4)


def attributed_pct(workspace: Workspace | None) -> float | None:
    if workspace is None:
        return None
    from analytics.challenge_metrics import unattributed_spend_pct

    unattr = unattributed_spend_pct(workspace)
    return round(max(0.0, min(100.0, 100.0 - float(unattr))), 1)


def fill_price_block(
    economics: dict[str, Any],
    *,
    semantics: dict[str, Any] | None,
    profile: dict[str, Any] | None,
    workspace: Workspace | None = None,
    capability_id: str | None = None,
    account_id: str | None = None,
    production_usd: float | None = None,
    risk_usd: float | None = None,
    n_verified: int | None = None,
    cost_basis: str | None = None,
) -> dict[str, Any]:
    """Attach floor/cap/list/risk onto an economics dict. Does not replace primary_metric_usd."""
    profile = profile or {}
    priors = profile.get("priors", {})
    mode = pricing_mode_for_profile(profile)
    label = primary_metric_label(semantics, economics.get("primary_metric_label") or "cost_of_leaving_live_usd")
    display = primary_metric_display(semantics)

    out = dict(economics)
    out["primary_metric_label"] = label
    if display:
        out["primary_metric_display"] = display
    out["pricing_mode"] = mode
    out["ranking_metric_usd"] = round(float(out.get("primary_metric_usd") or 0), 4)
    out["ranking_metric_label"] = label

    runs = _scoped_runs(workspace, capability_id=capability_id, account_id=account_id)
    if n_verified is None:
        n_verified = _n_verified(
            workspace, capability_id=capability_id, account_id=account_id
        )
    out["n_verified"] = int(n_verified)

    inference = 0.0
    if production_usd is None:
        if not runs.empty and "run_cost_usd" in runs.columns:
            inference = float(runs["run_cost_usd"].fillna(0).sum())
        hitl = _hitl_usd(workspace, runs, profile)
        production_usd = inference + hitl
    production_usd = float(production_usd or 0)

    basis = cost_basis if cost_basis in COST_BASIS_RANK else cost_basis_for_workspace(workspace)
    out["cost_basis"] = basis
    pct = attributed_pct(workspace)
    if pct is not None:
        out["attributed_pct"] = pct

    if n_verified > 0:
        out["floor_usd"] = round(production_usd / n_verified, 4)
    # else: omit floor_usd — refuse a fake $0.00

    if risk_usd is not None:
        if n_verified > 0:
            out["risk_usd"] = round(float(risk_usd) / n_verified, 4)
        else:
            out["risk_usd"] = round(float(risk_usd), 4)

    cap = priors.get("policy_cpso_cap")
    if mode == "internal_budget":
        cap = priors.get("budget_cap_per_outcome_usd", cap)
        baseline = priors.get("human_baseline_usd")
        if baseline is not None:
            out["baseline_usd"] = round(float(baseline), 4)
        # list_usd deliberately absent
        if "list_usd" in out:
            del out["list_usd"]
        if out.get("floor_usd") is not None and baseline is not None:
            out["margin_usd"] = round(float(baseline) - float(out["floor_usd"]), 4)
    elif mode == "product_sku":
        listed = _implied_list_usd(workspace, profile, runs, n_verified)
        if listed is not None:
            out["list_usd"] = listed
            out["list_basis"] = "implied"
            out["charged_usd"] = listed
            out["charged_basis"] = "reconstructed"
        if out.get("floor_usd") is not None and out.get("charged_usd") is not None:
            out["margin_usd"] = round(float(out["charged_usd"]) - float(out["floor_usd"]), 4)
    else:  # marketplace_take
        take = _marketplace_take_usd(workspace, capability_id=capability_id, n_verified=n_verified)
        if take is not None:
            out["charged_usd"] = take
            out["charged_basis"] = "reconstructed"
        if "list_usd" in out:
            del out["list_usd"]
        if out.get("floor_usd") is not None and out.get("charged_usd") is not None:
            out["margin_usd"] = round(float(out["charged_usd"]) - float(out["floor_usd"]), 4)

    if cap is not None:
        out["cap_usd"] = round(float(cap), 4)

    out["currency"] = out.get("currency") or "USD"
    return out


def format_usd(amount: float) -> str:
    """Enough decimals that a token-oracle floor ($0.003) is not rounded to $0.00."""
    n = float(amount)
    if abs(n) >= 1:
        return f"${n:.2f}"
    if abs(n) >= 0.01:
        return f"${n:.3f}"
    return f"${n:.4f}"


def price_sentence(economics: dict[str, Any], evidence: dict[str, Any] | None = None) -> str:
    """Operator-facing sentence. Missing fields are skipped, not invented."""
    mode = economics.get("pricing_mode") or "internal_budget"
    claim = (evidence or {}).get("claim_type")
    n = economics.get("n_verified")
    floor = economics.get("floor_usd")
    cap = economics.get("cap_usd")
    basis = economics.get("cost_basis")
    pct = economics.get("attributed_pct")
    parts: list[str] = []
    if floor is not None:
        attr = f", {pct:.0f}% attributed" if pct is not None else ""
        parts.append(f"floor {format_usd(floor)} ({basis or 'unknown'}{attr})")
    else:
        parts.append("floor unavailable (no verified outcomes)")
    if cap is not None:
        cap_word = "budget cap" if mode == "internal_budget" else "cap"
        parts.append(f"{cap_word} {format_usd(cap)}")
    if mode == "product_sku" and economics.get("list_usd") is not None:
        lb = economics.get("list_basis") or "implied"
        parts.append(f"list {format_usd(economics['list_usd'])} ({lb})")
    elif mode == "internal_budget" and economics.get("baseline_usd") is not None:
        parts.append(f"human baseline {format_usd(economics['baseline_usd'])}")
    elif mode == "marketplace_take" and economics.get("charged_usd") is not None:
        parts.append(f"take {format_usd(economics['charged_usd'])} (implied)")
    if claim:
        n_bit = f", n={n}" if n else ""
        parts.append(f"claim_type {claim}{n_bit}")
    return "; ".join(parts)
