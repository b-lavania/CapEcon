"""Principal-Agent delegation economics.

Net Delegated Surplus = Value(Verified) × P(Success) − C_inference − C_verification − Risk(Harm)
Agency Deficit fires when inference + review > human baseline.
SPRT spot-check recommendation: how many approvals can you safely skip?
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from core.workspace import Workspace


def compute_agency_surplus(
    ws: Workspace,
    *,
    human_baseline_usd: float | None = None,
    reviewer_hourly_usd: float | None = None,
    review_minutes: float | None = None,
) -> dict[str, Any]:
    """
    Compute delegation surplus vs human baseline.

    Returns:
        inference_cost_usd     — mean run_cost_usd from runs
        verification_cost_usd  — loaded HITL cost per run (labor)
        human_baseline_usd     — reference labor cost
        agency_surplus_usd     — (human_baseline - inference - verification) per run
        agency_deficit         — bool, True when agent costs more than baseline
        claim_type             — from workspace meta
    """
    profile = ws.profile or {}
    priors = profile.get("priors", {})

    h_baseline = human_baseline_usd if human_baseline_usd is not None else float(priors.get("human_baseline_usd") or 0.0)
    r_hourly = reviewer_hourly_usd if reviewer_hourly_usd is not None else float(priors.get("reviewer_loaded_hourly_usd") or 85.0)
    r_mins = review_minutes if review_minutes is not None else float(priors.get("review_minutes_per_approval") or 4.0)

    runs = ws.runs
    approvals = ws.approvals

    inf_cost = float(runs["run_cost_usd"].mean()) if not runs.empty and "run_cost_usd" in runs.columns else 0.0

    n_approvals = len(approvals) if approvals is not None and not approvals.empty else 0
    n_runs = max(len(runs), 1)
    review_cost_per_run = (n_approvals / n_runs) * (r_hourly / 60.0 * r_mins)

    surplus = h_baseline - inf_cost - review_cost_per_run
    src = (ws.meta or {}).get("data_source", "synthetic")
    claim_type = "simulated" if src in ("synthetic", None, "") else "associational"

    return {
        "inference_cost_usd": round(inf_cost, 6),
        "verification_cost_usd": round(review_cost_per_run, 6),
        "human_baseline_usd": h_baseline,
        "agency_surplus_usd": round(surplus, 4),
        "agency_deficit": surplus < 0,
        "claim_type": claim_type,
    }


def sprt_spot_check_threshold(
    ws: Workspace,
    *,
    alpha: float = 0.05,
    beta: float = 0.10,
    p0_harm: float = 0.02,
    p1_harm: float = 0.06,
) -> dict[str, Any]:
    """
    Sequential probability ratio test parameters for relaxing 100% HITL to spot-check.
    Returns sample_size needed and whether spot-check is safe given current harm rate.
    """
    runs = ws.runs
    if runs.empty:
        return {"spot_check_safe": False, "n_needed": None, "current_harm_rate": None}

    harm_rate = float(runs["trust_incident"].mean()) if "trust_incident" in runs.columns else 0.0
    p_bar = (p0_harm + p1_harm) / 2
    n_needed = int(
        np.ceil(((1.645 + 1.28) ** 2 * p_bar * (1 - p_bar)) / ((p1_harm - p0_harm) ** 2))
    )
    spot_check_safe = harm_rate <= p0_harm and len(runs) >= n_needed

    return {
        "spot_check_safe": spot_check_safe,
        "n_needed": n_needed,
        "current_harm_rate": round(harm_rate, 4),
        "p0_harm": p0_harm,
        "p1_harm": p1_harm,
    }
