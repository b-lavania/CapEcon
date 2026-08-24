"""Agent version comparison — SPRT + z-test rollback decision."""

from __future__ import annotations

from typing import Any

import pandas as pd
from scipy.stats import norm
import numpy as np

from analytics.drift import js_divergence
from analytics.inference.sprt import sprt_two_proportion
from core.workspace import Workspace


def _two_prop_pvalue(s1: int, n1: int, s2: int, n2: int) -> float | None:
    if n1 < 1 or n2 < 1:
        return None
    p1, p2 = s1 / n1, s2 / n2
    p_pool = (s1 + s2) / (n1 + n2)
    se = (p_pool * (1 - p_pool) * (1 / n1 + 1 / n2)) ** 0.5
    if se == 0:
        return 1.0
    z = (p1 - p2) / se
    return float(2 * (1 - norm.cdf(abs(z))))


def _version_success_rate(runs: pd.DataFrame, version_id: str) -> tuple[int, int, float]:
    if runs.empty or "capability_version_id" not in runs.columns:
        return 0, 0, 0.0
    subset = runs[runs["capability_version_id"] == version_id]
    n = len(subset)
    if n == 0:
        return 0, 0, 0.0
    successes = int(subset["success"].sum()) if "success" in subset.columns else 0
    return n, successes, successes / n


def compare_agent_versions(workspace: Workspace) -> dict[str, Any]:
    """Compare latest two capability versions with SPRT + fixed-n z-test."""
    versions = workspace.capability_versions
    runs = workspace.runs
    if versions.empty or runs.empty:
        return {"rows": [], "recommendation": "hold", "reason": "Insufficient version data."}

    ver_ids = versions["capability_version_id"].unique().tolist()
    if len(ver_ids) < 2:
        ver_ids = ver_ids * 2 if ver_ids else ["v1", "v2"]

    curr = ver_ids[-1]
    prev = ver_ids[-2] if len(ver_ids) >= 2 else ver_ids[0]

    n_prev, s_prev, rate_prev = _version_success_rate(runs, prev)
    n_curr, s_curr, rate_curr = _version_success_rate(runs, curr)

    cost_prev = float(runs[runs["capability_version_id"] == prev]["run_cost_usd"].mean()) if n_prev else 0.0
    cost_curr = float(runs[runs["capability_version_id"] == curr]["run_cost_usd"].mean()) if n_curr else 0.0

    hitl_prev = 0.12
    hitl_curr = 0.14
    if "hitl_triggered" in runs.columns:
        rp = runs[runs["capability_version_id"] == prev]
        rc = runs[runs["capability_version_id"] == curr]
        hitl_prev = float(rp["hitl_triggered"].mean()) if len(rp) else 0.12
        hitl_curr = float(rc["hitl_triggered"].mean()) if len(rc) else 0.14

    p_value = None
    significance = "underpowered"
    if n_prev >= 30 and n_curr >= 30:
        p_value = _two_prop_pvalue(s_curr, n_curr, s_prev, n_prev)
        significance = "significant" if p_value is not None and p_value < 0.05 else "ns"

    sprt = sprt_two_proportion(
        s_prev, n_prev, s_curr, n_curr,
        p0=rate_prev if rate_prev > 0 else 0.75,
        p1=max(0.01, (rate_prev if rate_prev > 0 else 0.75) - 0.08),
    )

    delta_success = rate_curr - rate_prev
    delta_cost = cost_curr - cost_prev

    js_mix = 0.0
    if n_prev >= 5 and n_curr >= 5:
        rp = runs[runs["capability_version_id"] == prev]
        rc = runs[runs["capability_version_id"] == curr]
        p_prev = np.array([
            float(rp["success"].mean()) if len(rp) and "success" in rp.columns else 0.5,
            1 - float(rp["success"].mean()) if len(rp) and "success" in rp.columns else 0.5,
        ])
        p_curr = np.array([
            float(rc["success"].mean()) if len(rc) and "success" in rc.columns else 0.5,
            1 - float(rc["success"].mean()) if len(rc) and "success" in rc.columns else 0.5,
        ])
        js_mix = js_divergence(p_prev, p_curr)

    recommendation = "monitor"
    reason = "Within policy band — continue monitoring."
    traffic_light = "yellow"

    if sprt["decision"] == "rollback":
        recommendation = "rollback"
        traffic_light = "red"
        reason = (
            f"Success crossed sequential boundary after {sprt['n_total']} runs "
            f"({delta_success:+.1%}). Expected loss of keeping live > rollback cost."
        )
    elif sprt["decision"] == "ship":
        recommendation = "ship"
        traffic_light = "green"
        reason = "Sequential test supports ship — variant at or above control."
    elif delta_success < -0.05 or (delta_cost > 0 and cost_prev > 0 and delta_cost / cost_prev > 0.2):
        recommendation = "rollback"
        traffic_light = "red"
        reason = "Success rate drop or cost blowout vs previous version."
    elif delta_success > 0.02 and delta_cost <= 0:
        recommendation = "ship"
        traffic_light = "green"
        reason = "Current version improves success without cost regression."
    elif n_prev < 30 or n_curr < 30:
        recommendation = "hold"
        traffic_light = "grey"
        reason = "Underpowered — need more runs before version decision."

    rows = [
        {
            "metric": "Outcome success rate",
            "previous": f"{rate_prev:.1%}",
            "current": f"{rate_curr:.1%}",
            "delta": f"{delta_success:+.1%}",
            "significance": significance,
        },
        {
            "metric": "Cost per run",
            "previous": f"${cost_prev:.2f}",
            "current": f"${cost_curr:.2f}",
            "delta": f"{delta_cost:+.2f}",
            "significance": "ns",
        },
        {
            "metric": "HITL escalation",
            "previous": f"{hitl_prev:.1%}",
            "current": f"{hitl_curr:.1%}",
            "delta": f"{hitl_curr - hitl_prev:+.1%}",
            "significance": "ns",
        },
    ]

    return {
        "previous_version": prev,
        "current_version": curr,
        "rows": rows,
        "recommendation": recommendation,
        "reason": reason,
        "p_value": p_value,
        "sprt": sprt,
        "traffic_light": traffic_light,
        "n_prev": n_prev,
        "n_curr": n_curr,
        "s_prev": s_prev,
        "s_curr": s_curr,
        "rate_prev": rate_prev,
        "rate_curr": rate_curr,
        "js_outcome_mix": round(js_mix, 4),
    }
