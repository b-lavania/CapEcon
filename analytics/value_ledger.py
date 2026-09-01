"""Value ledger — demand-side task value on GDR economics."""

from __future__ import annotations

from typing import Any

import pandas as pd

from analytics.price_block import _n_verified, _scoped_runs, format_usd
from core.workspace import Workspace


def outcome_contract(workspace: Workspace | None) -> dict[str, Any]:
    if workspace is None:
        return {}
    return dict((workspace.meta or {}).get("outcome_contract") or {})


def sync_outcome_contract_to_workspace(ws: Workspace, contract: dict[str, Any] | None) -> None:
    if contract is None:
        return
    ws.meta = dict(ws.meta or {})
    ws.meta["outcome_contract"] = contract


def _scoped_verified_outcomes(
    workspace: Workspace | None,
    *,
    capability_id: str | None = None,
    account_id: str | None = None,
) -> pd.DataFrame:
    if workspace is None:
        return pd.DataFrame()
    outcomes = getattr(workspace, "outcomes", pd.DataFrame())
    if outcomes is None or outcomes.empty:
        return pd.DataFrame()
    scoped_runs = _scoped_runs(workspace, capability_id=capability_id, account_id=account_id)
    run_ids = (
        set(scoped_runs["run_id"].astype(str))
        if not scoped_runs.empty and "run_id" in scoped_runs.columns
        else None
    )
    verified = outcomes.copy()
    if "verified" in verified.columns and "success" in verified.columns:
        verified = verified[verified["verified"].astype(bool) & verified["success"].astype(bool)]
    elif "verified" in verified.columns:
        verified = verified[verified["verified"].astype(bool)]
    if run_ids is not None and "agent_run_id" in verified.columns:
        verified = verified[verified["agent_run_id"].astype(str).isin(run_ids)]
    if account_id and "account_id" in verified.columns:
        verified = verified[verified["account_id"].astype(str) == str(account_id)]
    return verified


def rollup_outcome_value(
    workspace: Workspace | None,
    *,
    capability_id: str | None = None,
    account_id: str | None = None,
) -> float:
    verified = _scoped_verified_outcomes(
        workspace, capability_id=capability_id, account_id=account_id
    )
    if verified.empty or "outcome_value_usd" not in verified.columns:
        return 0.0
    vals = pd.to_numeric(verified["outcome_value_usd"], errors="coerce").fillna(0)
    return float(vals.sum())


def time_saved_value(
    workspace: Workspace | None,
    profile: dict[str, Any] | None,
    *,
    capability_id: str | None = None,
    account_id: str | None = None,
) -> float:
    if workspace is None:
        return 0.0
    priors = (profile or {}).get("priors", {})
    baseline_min = float(priors.get("human_baseline_minutes", 0) or 0)
    if baseline_min <= 0:
        return 0.0
    hourly = float(priors.get("reviewer_loaded_hourly_usd", 0) or priors.get("human_baseline_usd", 0) or 0)
    if hourly <= 0:
        return 0.0
    runs = _scoped_runs(workspace, capability_id=capability_id, account_id=account_id)
    if runs.empty:
        return 0.0
    minutes_per_step = float(priors.get("minutes_per_agent_step", 0.5) or 0.5)
    if "steps" in runs.columns:
        agent_min = float(runs["steps"].fillna(1).sum()) * minutes_per_step
    else:
        agent_min = float(len(runs)) * minutes_per_step
    saved = max(0.0, baseline_min * len(runs) - agent_min)
    return round(saved * hourly / 60.0, 4)


def revenue_attributed(
    workspace: Workspace | None,
    *,
    capability_id: str | None = None,
    account_id: str | None = None,
) -> float:
    if workspace is None:
        return 0.0
    verified = _scoped_verified_outcomes(
        workspace, capability_id=capability_id, account_id=account_id
    )
    if verified.empty:
        return 0.0
    txs = getattr(workspace, "transactions", pd.DataFrame())
    if txs is None or txs.empty:
        subs = getattr(workspace, "subscriptions", pd.DataFrame())
        if subs is not None and not subs.empty and account_id and "mrr_usd" in subs.columns:
            row = subs[subs["account_id"].astype(str) == str(account_id)]
            if not row.empty:
                return float(row["mrr_usd"].iloc[0]) / max(len(verified), 1)
        return 0.0
    total = 0.0
    if "amount_usd" in txs.columns and "account_id" in verified.columns:
        accts = set(verified["account_id"].astype(str))
        sub = txs[txs["account_id"].astype(str).isin(accts)] if "account_id" in txs.columns else txs
        total = float(pd.to_numeric(sub["amount_usd"], errors="coerce").fillna(0).sum())
    return round(total, 4)


def prior_value_from_contract(
    workspace: Workspace | None,
    contract: dict[str, Any],
    *,
    capability_id: str | None = None,
    account_id: str | None = None,
) -> tuple[float, list[dict[str, Any]]]:
    value_map = contract.get("outcome_value_map") or {}
    if not value_map:
        return 0.0, []
    verified = _scoped_verified_outcomes(
        workspace, capability_id=capability_id, account_id=account_id
    )
    if verified.empty or "outcome_type" not in verified.columns:
        return 0.0, []
    total = 0.0
    rows: list[dict[str, Any]] = []
    for otype, default_usd in value_map.items():
        try:
            rate = float(default_usd or 0)
        except (TypeError, ValueError):
            continue
        if rate <= 0:
            continue
        count = int((verified["outcome_type"].astype(str) == str(otype)).sum())
        if count:
            amt = rate * count
            total += amt
            rows.append({"label": f"prior_{otype}", "amount_usd": round(amt, 4), "notes": f"{count}× @ ${rate}"})
    return round(total, 4), rows


def task_tier_list_usd(contract: dict[str, Any]) -> float | None:
    tier = contract.get("task_tier")
    if not tier:
        return None
    tiers = contract.get("task_tiers") or {}
    spec = tiers.get(tier) or {}
    listed = spec.get("list_usd")
    if listed is None:
        return None
    try:
        return float(listed)
    except (TypeError, ValueError):
        return None


def fill_value_block(
    economics: dict[str, Any],
    *,
    workspace: Workspace | None = None,
    profile: dict[str, Any] | None = None,
    capability_id: str | None = None,
    account_id: str | None = None,
) -> dict[str, Any]:
    """Attach value_usd / surplus_usd using rollup precedence rules."""
    out = dict(economics)
    n_verified = int(out.get("n_verified") or _n_verified(
        workspace, capability_id=capability_id, account_id=account_id
    ))
    if n_verified == 0:
        return out

    profile = profile or {}
    priors = profile.get("priors", {})
    contract = outcome_contract(workspace)
    tier_list = task_tier_list_usd(contract)
    if tier_list is not None:
        out["tier_list_usd"] = round(tier_list, 4)

    breakdown: list[dict[str, Any]] = []
    value_basis: str | None = None

    observed = rollup_outcome_value(
        workspace, capability_id=capability_id, account_id=account_id
    )
    if observed > 0:
        breakdown.append({
            "label": "outcome_value_usd",
            "amount_usd": round(observed, 4),
            "notes": "sum on verified successful outcomes",
        })
        value_basis = "observed"
    else:
        rev = revenue_attributed(
            workspace, capability_id=capability_id, account_id=account_id
        )
        time_saved = time_saved_value(
            workspace, profile, capability_id=capability_id, account_id=account_id
        )
        estimated = 0.0
        if rev > 0:
            breakdown.append({"label": "revenue_attributed", "amount_usd": rev, "notes": "transactions/subscriptions"})
            estimated += rev
        if time_saved > 0 and rev == 0:
            breakdown.append({"label": "time_saved", "amount_usd": time_saved, "notes": "human baseline minutes saved"})
            estimated += time_saved
        if estimated > 0:
            value_basis = "estimated"
        else:
            prior_total, prior_rows = prior_value_from_contract(
                workspace, contract, capability_id=capability_id, account_id=account_id
            )
            if prior_total > 0:
                breakdown.extend(prior_rows)
                value_basis = "prior"

    include_error = bool(priors.get("include_error_avoided_in_value", False))
    if workspace is not None:
        catastrophes = getattr(workspace, "catastrophic_events", pd.DataFrame())
        if catastrophes is not None and not catastrophes.empty and "cost_usd" in catastrophes.columns:
            err_cost = float(pd.to_numeric(catastrophes["cost_usd"], errors="coerce").fillna(0).sum())
            if err_cost > 0:
                row = {
                    "label": "error_avoided",
                    "amount_usd": round(err_cost, 4),
                    "notes": "associational — catastrophic events avoided",
                }
                breakdown.append(row)
                if include_error and value_basis:
                    pass  # headline sum below handles inclusion

    headline_rows = [b for b in breakdown if b["label"] != "error_avoided" or include_error]
    if not headline_rows:
        return out

    value_usd = round(sum(float(b["amount_usd"]) for b in headline_rows), 4)
    out["value_usd"] = value_usd
    out["value_basis"] = value_basis or "estimated"
    out["value_breakdown"] = breakdown

    floor = out.get("floor_usd")
    if floor is not None and n_verified > 0:
        surplus = value_usd - float(floor) * n_verified
        out["surplus_usd"] = round(surplus / n_verified, 4)

    return out


def value_sentence(economics: dict[str, Any], evidence: dict[str, Any] | None = None) -> str:
    """Operator-facing value caption. Omit when value_usd missing."""
    value = economics.get("value_usd")
    if value is None:
        return ""
    basis = economics.get("value_basis") or "estimated"
    n = economics.get("n_verified")
    parts = [f"value {format_usd(value)} ({basis}"]
    if n:
        parts[0] += f", n={n}"
    parts[0] += ")"
    surplus = economics.get("surplus_usd")
    if surplus is not None:
        sign = "+" if surplus >= 0 else ""
        parts.append(f"surplus {sign}{format_usd(surplus)} vs floor")
    claim = (evidence or {}).get("claim_type")
    if claim:
        parts.append(f"claim_type {claim}")
    return "; ".join(parts)
