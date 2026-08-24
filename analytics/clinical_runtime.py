"""Clinical-runtime economics and summary chips."""

from __future__ import annotations

from typing import Any

import pandas as pd

from analytics.queueing import erlang_c
from core.workspace import Workspace


def _clinical(ws: Workspace) -> pd.DataFrame:
    return getattr(ws, "clinical_runs", pd.DataFrame())


def clinical_summary_chips(ws: Workspace) -> dict[str, Any]:
    cr = _clinical(ws)
    if cr.empty:
        return {
            "n_runs": 0,
            "phi_log_rate": 0.0,
            "mean_abstention": 0.0,
            "review_backlog_hr": 0.0,
            "fhir_integrity_rate": 1.0,
            "inference_usd": 0.0,
            "review_labor_usd": 0.0,
        }
    priors = ws.profile.get("priors", {})
    arrival = float(cr.attrs.get("review_arrival_per_hr", priors.get("review_arrival_per_hr", 18.0)))
    service = float(cr.attrs.get("review_service_per_hr", priors.get("review_service_per_hr", 6.0)))
    servers = max(1, int(priors.get("reviewer_count", 3)))
    queue = erlang_c(arrival, service, servers)
    pending = cr[cr["review_required"] & ~cr["review_completed"]]
    backlog = float(pending["review_wait_hr"].mean()) if not pending.empty else 0.0

    return {
        "n_runs": len(cr),
        "phi_log_rate": float(cr["phi_in_logs"].mean()),
        "mean_abstention": float(cr["abstention_rate"].mean()),
        "review_backlog_hr": backlog,
        "fhir_integrity_rate": float(cr["fhir_integrity_ok"].mean()),
        "inference_usd": float(cr["inference_usd"].sum()),
        "review_labor_usd": float(cr["review_labor_usd"].sum()),
        "p_wait": queue.get("p_wait", 0.0),
    }


def capability_clinical_economics(ws: Workspace, capability_id: str) -> dict[str, float]:
    cr = _clinical(ws)
    sub = cr[cr["capability_id"] == capability_id] if not cr.empty else cr
    if sub.empty:
        return {"inference_usd": 0.0, "review_labor_usd": 0.0, "expected_harm_usd": 0.0, "total_usd": 0.0}
    priors = ws.profile.get("priors", {})
    harm_unit = float(priors.get("clinical_harm_unit_usd", 8500.0))
    phi_rate = float(sub["phi_in_logs"].mean())
    abstention = float(sub["abstention_rate"].mean())
    harm_prob = min(0.35, phi_rate * 0.9 + max(0.0, 0.25 - abstention) * 0.4)
    inference = float(sub["inference_usd"].sum())
    labor = float(sub["review_labor_usd"].sum())
    harm = harm_prob * harm_unit * max(1, len(sub) // 50)
    return {
        "inference_usd": round(inference, 2),
        "review_labor_usd": round(labor, 2),
        "expected_harm_usd": round(harm, 2),
        "total_usd": round(inference + labor + harm, 2),
    }
