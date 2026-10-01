"""Token production efficiency: MOPT, token bloat, cascade opportunity.

Reads run_cost_usd from ws.runs (already computed by analytics/economics.py).
Does NOT reprice tokens. Computes productivity ratios and diminishing-returns curves.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from core.workspace import Workspace


def marginal_outcome_per_token(runs: pd.DataFrame) -> dict[str, Any]:
    """
    Estimate MOPT = ΔSuccess / Δ(tokens_in).
    Uses log-linear regression on (tokens, success) per capability.
    Returns dict: {capability_id -> {"mopt": float, "saturation": bool, "n": int, "mean_cost_usd": float}}
    """
    required = {"run_id", "capability_id", "tokens_in", "success", "run_cost_usd"}
    if runs.empty or not required.issubset(runs.columns):
        return {}
    out: dict[str, Any] = {}
    for cap_id, grp in runs.groupby("capability_id"):
        grp = grp.dropna(subset=["tokens_in", "success"])
        if len(grp) < 10:
            continue
        x = np.log1p(grp["tokens_in"].astype(float).values)
        y = grp["success"].astype(float).values
        if np.std(x) < 1e-6:
            continue
        slope = float(np.cov(x, y)[0, 1] / np.var(x))
        saturation = slope < 0.005  # near-zero marginal return
        out[str(cap_id)] = {
            "mopt": round(slope, 6),
            "saturation": saturation,
            "n": len(grp),
            "mean_cost_usd": round(float(grp["run_cost_usd"].mean()), 6),
        }
    return out


def token_bloat_flags(ws: Workspace) -> pd.DataFrame:
    """
    Return capabilities where token cost is high but MOPT is in saturation.
    Columns: capability_id, mean_cost_usd, mopt, saturation, flag.
    """
    cols = ["capability_id", "mean_cost_usd", "mopt", "saturation", "flag"]
    runs = ws.runs
    if runs.empty:
        return pd.DataFrame(columns=cols)
    mopt = marginal_outcome_per_token(runs)
    if not mopt:
        return pd.DataFrame(columns=cols)
    rows = []
    costs = [v["mean_cost_usd"] for v in mopt.values()]
    p75_cost = float(np.percentile(costs, 75)) if costs else 0.0
    for cap_id, stats in mopt.items():
        flag = stats["saturation"] and stats["mean_cost_usd"] >= p75_cost
        rows.append(
            {
                "capability_id": cap_id,
                "mean_cost_usd": stats["mean_cost_usd"],
                "mopt": stats["mopt"],
                "saturation": stats["saturation"],
                "flag": flag,
            }
        )
    return pd.DataFrame(rows)


def cascade_opportunity(
    ws: Workspace,
    *,
    lite_cost_fraction: float = 0.05,
    quality_floor_success_rate: float = 0.82,
) -> dict[str, Any]:
    """
    Estimate cost savings if saturated capabilities down-routed to lite model.
    Returns {"savings_usd": float, "candidates": list[str], "n_candidates": int, "claim_type": str}.
    """
    runs = ws.runs
    if runs.empty or "run_cost_usd" not in runs.columns:
        return {"savings_usd": 0.0, "candidates": [], "n_candidates": 0, "claim_type": "simulated"}
    flags = token_bloat_flags(ws)
    if flags.empty:
        candidates: list[str] = []
    else:
        candidates = flags.loc[flags["flag"], "capability_id"].tolist()
    savings = 0.0
    for cap_id in candidates:
        sub = runs[runs["capability_id"] == cap_id]
        sr = float(sub["success"].mean()) if "success" in sub.columns else 0.0
        if sr >= quality_floor_success_rate:
            cost = float(sub["run_cost_usd"].sum())
            savings += cost * (1.0 - lite_cost_fraction)
    return {
        "savings_usd": round(savings, 2),
        "candidates": candidates,
        "n_candidates": len(candidates),
        "claim_type": (ws.meta or {}).get("claim_type", "simulated"),
    }
