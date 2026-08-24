"""Ingest golden OTel fixture → Version Gate GDR with claim_type."""

from pathlib import Path

import pytest

from analytics.agentic_profile import get_preset
from analytics.version_gate import evaluate_version_gate
from core.workspace import build_workspace
from data.adapters.otel import ingest_otel_export
from data.adapters.scrub import span_has_content

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "golden_otel.jsonl"


def test_ingest_fixture_to_version_gate():
    tables = ingest_otel_export(FIXTURE)
    for rec in tables["spans"].to_dict(orient="records"):
        assert not span_has_content(rec)

    ws = build_workspace(
        get_preset("assistant_heavy"),
        seed=42,
        n_sessions=80,
        data_source="uploaded",
        uploaded_tables={"spans": tables["spans"], "runs": tables["runs"]},
    )
    assert ws.meta.get("data_source") == "uploaded"
    assert not ws.spans.empty
    gate = evaluate_version_gate(ws)
    assert gate["gdr"]["evidence"]["claim_type"] in ("associational", "simulated", "causal")
    assert gate["recommended_action"] in ("ship", "hold", "rollback", "monitor", "revise", "throttle")
    assert "ci_status" in gate
