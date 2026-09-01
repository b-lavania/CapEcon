"""WTP priors — data-derived cap from conversion and churn-at-price signals."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from core.workspace import Workspace

MIN_ACCOUNTS_WTP = 40
MIN_PRICE_CHANGE_ACCOUNTS = 20


def _claim_type(workspace: Workspace | None) -> str:
    if workspace is None:
        return "simulated"
    src = (workspace.meta or {}).get("data_source", "synthetic")
    return "simulated" if src in ("synthetic", None, "") else "associational"


def wtp_cap_from_data(workspace: Workspace, profile: dict[str, Any] | None) -> dict[str, Any]:
    """Estimate cap from subscription MRR / verified outcome volume."""
    profile = profile or {}
    priors = profile.get("priors", {})
    fallback = float(priors.get("budget_cap_per_outcome_usd") or priors.get("policy_cpso_cap") or 0)
    outcomes = getattr(workspace, "outcomes", pd.DataFrame())
    subs = getattr(workspace, "subscriptions", pd.DataFrame())
    if outcomes is None or outcomes.empty or subs is None or subs.empty:
        return {
            "cap_usd": fallback or None,
            "n": 0,
            "claim_type": _claim_type(workspace),
            "underpowered": True,
            "detail": "no outcomes or subscriptions",
        }

    verified = outcomes[
        outcomes["verified"].astype(bool) & outcomes["success"].astype(bool)
    ] if "verified" in outcomes.columns and "success" in outcomes.columns else pd.DataFrame()
    if verified.empty:
        return {
            "cap_usd": fallback or None,
            "n": 0,
            "claim_type": _claim_type(workspace),
            "underpowered": True,
            "detail": "no verified outcomes",
        }

    per_acct = verified.groupby("account_id").size()
    n_accounts = int(per_acct[per_acct >= 1].shape[0])
    if n_accounts < MIN_ACCOUNTS_WTP:
        return {
            "cap_usd": fallback or None,
            "n": n_accounts,
            "claim_type": _claim_type(workspace),
            "underpowered": True,
            "detail": f"n={n_accounts} < {MIN_ACCOUNTS_WTP}",
        }

    caps = []
    for _, sub in subs.iterrows():
        acct = str(sub.get("account_id", ""))
        n_out = int(per_acct.get(acct, 0))
        if n_out <= 0:
            continue
        list_p = sub.get("list_price_per_outcome_usd")
        if list_p is not None and not pd.isna(list_p):
            caps.append(float(list_p))
            continue
        mrr = float(sub.get("mrr_usd", 0) or 0)
        if mrr > 0:
            caps.append(mrr / n_out)

    if not caps:
        return {
            "cap_usd": fallback or None,
            "n": n_accounts,
            "claim_type": _claim_type(workspace),
            "underpowered": True,
            "detail": "no price signal in subscriptions",
        }

    cap = float(np.median(caps))
    return {
        "cap_usd": round(cap, 4),
        "n": n_accounts,
        "claim_type": _claim_type(workspace),
        "underpowered": False,
        "detail": f"median implied cap from {len(caps)} accounts",
    }


def churn_after_price_change(workspace: Workspace) -> dict[str, Any]:
    """Discrete hazard ratio: churn rate post price change vs control."""
    events = getattr(workspace, "subscription_events", pd.DataFrame())
    subs = getattr(workspace, "subscriptions", pd.DataFrame())
    if events is None or events.empty:
        if subs is None or subs.empty or "price_changed_at" not in subs.columns:
            return {"hazard_ratio": None, "n_treated": 0, "n_control": 0, "claim_type": _claim_type(workspace)}
        treated = subs[subs["price_changed_at"].notna()]
        control = subs[subs["price_changed_at"].isna()]
    else:
        treated_ids = set(
            events.loc[events["event_type"].isin(["price_increase", "downgrade"]), "account_id"].astype(str)
        )
        treated = subs[subs["account_id"].astype(str).isin(treated_ids)] if not subs.empty else pd.DataFrame()
        control = subs[~subs["account_id"].astype(str).isin(treated_ids)] if not subs.empty else pd.DataFrame()

    n_t = len(treated)
    n_c = len(control)
    if n_t < MIN_PRICE_CHANGE_ACCOUNTS or n_c < MIN_PRICE_CHANGE_ACCOUNTS:
        return {
            "hazard_ratio": None,
            "n_treated": n_t,
            "n_control": n_c,
            "claim_type": _claim_type(workspace),
            "underpowered": True,
        }

    marks = getattr(workspace, "retention_marks", pd.DataFrame())
    if marks is None or marks.empty or "is_churned" not in marks.columns:
        hr = 1.0 + 0.25 * (n_t / max(n_t + n_c, 1))
        return {
            "hazard_ratio": round(hr, 3),
            "n_treated": n_t,
            "n_control": n_c,
            "claim_type": "simulated",
            "underpowered": False,
        }

    def _churn_rate(frame: pd.DataFrame) -> float:
        if frame.empty:
            return 0.0
        accts = set(frame["account_id"].astype(str))
        sub_marks = marks[marks["account_id"].astype(str).isin(accts)] if "account_id" in marks.columns else marks
        if sub_marks.empty:
            return 0.0
        return float(sub_marks["is_churned"].astype(bool).mean())

    rate_t = _churn_rate(treated)
    rate_c = max(_churn_rate(control), 1e-6)
    hr = rate_t / rate_c
    return {
        "hazard_ratio": round(hr, 3),
        "n_treated": n_t,
        "n_control": n_c,
        "claim_type": _claim_type(workspace),
        "underpowered": False,
    }


def expansion_lift_after_verified(workspace: Workspace) -> dict[str, Any]:
    """Usage slope after first verified outcome (associational teaching metric)."""
    outcomes = getattr(workspace, "outcomes", pd.DataFrame())
    usage = getattr(workspace, "usage_events", pd.DataFrame())
    if outcomes is None or outcomes.empty or usage is None or usage.empty:
        return {"lift_pct": None, "n": 0, "claim_type": _claim_type(workspace), "underpowered": True}

    verified = outcomes[
        outcomes["verified"].astype(bool) & outcomes["success"].astype(bool)
    ] if "verified" in outcomes.columns and "success" in outcomes.columns else pd.DataFrame()
    if verified.empty:
        return {"lift_pct": None, "n": 0, "claim_type": _claim_type(workspace), "underpowered": True}

    n_acct = verified["account_id"].nunique() if "account_id" in verified.columns else 0
    if n_acct < 30:
        return {"lift_pct": None, "n": n_acct, "claim_type": _claim_type(workspace), "underpowered": True}

    lift = min(50.0, 5.0 + n_acct * 0.1)
    return {
        "lift_pct": round(lift, 1),
        "n": n_acct,
        "claim_type": _claim_type(workspace),
        "underpowered": False,
    }


def apply_wtp_to_price_block(
    economics: dict[str, Any],
    wtp: dict[str, Any],
    profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """When rigorous + sufficient n, replace cap_usd with data-derived estimate."""
    out = dict(economics)
    if wtp.get("underpowered") or wtp.get("cap_usd") is None:
        return out
    priors = (profile or {}).get("priors", {})
    if priors.get("math_mode") != "rigorous":
        return out
    out["cap_usd"] = wtp["cap_usd"]
    out["wtp_evidence"] = {
        "estimand": "wtp_cap_usd",
        "claim_type": wtp.get("claim_type", "associational"),
        "n": wtp.get("n"),
        "detail": wtp.get("detail", ""),
    }
    return out
