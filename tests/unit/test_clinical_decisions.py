"""Clinical warehouse generator and GDR emit (slow round-trip)."""

import pytest

from analytics.agentic_profile import get_preset
from analytics.decisions import emit_clinical_records
from core.workspace import build_workspace
from data.ground_truth import get as get_ground_truth


@pytest.mark.slow
def test_clinical_runs_generated_for_openmed_preset():
    profile = get_preset("openmed_v22")
    ws = build_workspace(profile, seed=42, n_sessions=800)
    cr = ws.clinical_runs
    assert not cr.empty
    assert "pii_deidentify" in cr["capability_id"].values
    assert cr["phi_in_logs"].dtype == bool


@pytest.mark.slow
def test_capability_foreign_keys_after_catalog_injection():
    profile = get_preset("openmed_v22")
    ws = build_workspace(profile, seed=42, n_sessions=800)
    cap_ids = set(ws.capabilities["capability_id"])
    run_caps = set(ws.runs["capability_id"].dropna())
    assert run_caps.issubset(cap_ids)


@pytest.mark.slow
def test_emit_clinical_records_schema_and_metric():
    profile = get_preset("openmed_v22")
    ws = build_workspace(profile, seed=42, n_sessions=800)
    records = emit_clinical_records(ws, profile)
    assert records
    assert records[0]["vertical"] == "clinical_runtime"
    assert records[0]["economics"]["primary_metric_label"] == "residual_clinical_risk_usd"
    assert records[0]["economics"]["pricing_mode"] == "internal_budget"
    assert "list_usd" not in records[0]["economics"]
    assert "floor_usd" in records[0]["economics"]
    assert "risk_usd" in records[0]["economics"]
    breakdown = {b["label"] for b in records[0]["economics"]["breakdown"]}
    assert breakdown >= {"inference", "review_labor", "expected_harm"}
    costs = [r["economics"]["primary_metric_usd"] for r in records]
    assert costs == sorted(costs, reverse=True)


@pytest.mark.slow
def test_planted_clinical_negatives_in_ground_truth():
    profile = get_preset("openmed_v22")
    ws = build_workspace(profile, seed=42, n_sessions=800)
    gt = get_ground_truth(ws.seed)
    assert gt is not None
    assert "pii_deidentify" in gt.planted_clinical_negatives
    assert gt.planted_clinical_negatives["pii_deidentify"] == "phi_leakage"
