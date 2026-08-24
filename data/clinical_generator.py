"""Synthetic clinical-runtime evidence rows from agentic runs + case catalog."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

CLINICAL_COLS = [
    "clinical_run_id",
    "run_id",
    "capability_id",
    "occurred_at",
    "abstention_rate",
    "span_integrity",
    "phi_in_logs",
    "fhir_integrity_ok",
    "vocab_snapshot_hash",
    "vocab_snapshot_ok",
    "review_required",
    "review_completed",
    "review_wait_hr",
    "mime_quarantined",
    "prompt_injection_flag",
    "assertion_context_ok",
    "grounding_conflict",
    "inference_usd",
    "review_labor_usd",
]


def generate_clinical_runs(
    runs: pd.DataFrame,
    capabilities: pd.DataFrame,
    catalog: dict[str, Any],
    profile: dict[str, Any],
    *,
    seed: int = 42,
) -> pd.DataFrame:
    """Build PHI-safe clinical_runs from priced agentic runs."""
    priors = profile.get("priors", {})
    rng = np.random.default_rng(seed)
    review_cost = float(priors.get("review_labor_usd_per_run", 2.75))
    review_rate = float(priors.get("clinical_review_rate", 0.92))
    arrival_hr = float(priors.get("review_arrival_per_hr", 18.0))
    service_hr = float(priors.get("review_service_per_hr", 6.0))

    if runs.empty:
        return pd.DataFrame(columns=CLINICAL_COLS)

    planted = {
        str(p["capability_id"]): str(p["exception"])
        for p in (catalog.get("planted_negatives") or [])
        if p.get("capability_id")
    }
    cap_ids = set(capabilities["capability_id"].astype(str)) if not capabilities.empty else set()

    rows: list[dict[str, Any]] = []
    snapshot_base = "sha256:v22-pinned"

    for idx, run in runs.iterrows():
        cap_id = str(run.get("capability_id", ""))
        if cap_id not in cap_ids:
            continue
        ts = run.get("started_at", pd.Timestamp("2025-01-01"))
        inference = float(run.get("run_cost_usd", priors.get("run_cost_per_success", 0.5)))

        abstention = float(rng.uniform(0.35, 0.55))
        phi_logs = False
        fhir_ok = True
        vocab_ok = True
        grounding_conflict = False
        injection = False
        review_wait = float(rng.uniform(0.5, 2.5))

        neg = planted.get(cap_id)
        if neg == "phi_leakage":
            phi_logs = True
            abstention = float(rng.uniform(0.08, 0.14))
        elif neg == "abstention_collapse":
            abstention = float(rng.uniform(0.02, 0.08))
            review_wait = float(rng.uniform(6.0, 14.0))
        elif neg == "fhir_integrity_fail":
            fhir_ok = False
        elif neg == "vocab_snapshot_drift":
            vocab_ok = False
        elif neg == "run_cost_blowout":
            inference = inference * float(rng.uniform(2.2, 3.5))
        elif neg == "prompt_injection":
            injection = True

        if rng.random() < 0.04 and cap_id not in planted:
            grounding_conflict = True

        review_required = bool(rng.random() < review_rate or not fhir_ok or phi_logs)
        review_completed = review_required and rng.random() > 0.12
        if neg == "abstention_collapse":
            review_completed = rng.random() < 0.55

        labor = review_cost if review_required else 0.0
        if review_wait > 8.0:
            labor *= 1.35

        rows.append({
            "clinical_run_id": f"CLN-{idx + 1:06d}",
            "run_id": run.get("run_id"),
            "capability_id": cap_id,
            "occurred_at": ts,
            "abstention_rate": round(abstention, 4),
            "span_integrity": round(float(rng.uniform(0.88, 0.99)), 4),
            "phi_in_logs": phi_logs,
            "fhir_integrity_ok": fhir_ok,
            "vocab_snapshot_hash": f"{snapshot_base}-{cap_id[:8]}",
            "vocab_snapshot_ok": vocab_ok,
            "review_required": review_required,
            "review_completed": review_completed,
            "review_wait_hr": round(review_wait, 2),
            "mime_quarantined": bool(rng.random() < 0.03),
            "prompt_injection_flag": injection,
            "assertion_context_ok": fhir_ok and not grounding_conflict,
            "grounding_conflict": grounding_conflict,
            "inference_usd": round(inference, 3),
            "review_labor_usd": round(labor, 3),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=CLINICAL_COLS)

    from data.ground_truth import get, register

    gt = get(seed)
    if gt is not None:
        gt.planted_clinical_negatives = dict(planted)
        register(gt)

    df.attrs["review_arrival_per_hr"] = arrival_hr
    df.attrs["review_service_per_hr"] = service_hr
    return df
