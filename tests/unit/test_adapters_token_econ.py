"""Token-economics adapter tests."""

from pathlib import Path

from analytics.agentic_profile import get_preset
from core.control_plane import ingest_and_build
from data.adapters.token_econ import ingest_token_econ_export, ingest_token_econ_records

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "adapters" / "token_econ"


def test_token_econ_records_direct():
    records = [
        {
            "query_id": "QRY-TEST-1",
            "router_model": "test_router",
            "selected_tier": "flash_lite",
            "prompt_tokens": 500,
            "completion_tokens": 100,
            "cost_usd": 0.001,
            "verification_status": "verified",
        }
    ]
    pack = ingest_token_econ_records(records)
    assert pack["meta"]["evaluator_id"] == "capecon_token_econ_adapter"
    assert pack["meta"]["ingest_source"] == "token_econ"
    assert pack["meta"]["claim_type"] == "associational"

    assert "runs" in pack["tables"]
    assert "usage_events" in pack["tables"]
    assert "routing_log" in pack["tables"]

    runs = pack["tables"]["runs"]
    assert len(runs) == 1
    assert runs.iloc[0]["run_id"] == "QRY-TEST-1"
    assert runs.iloc[0]["success"] is True
    assert runs.iloc[0]["run_cost_usd"] == 0.001

    rlog = pack["tables"]["routing_log"]
    assert len(rlog) == 1
    assert rlog.iloc[0]["selected_tier"] == "flash_lite"


def test_routellm_cascade_fixture_builds_workspace():
    fixture_path = FIXTURES / "routellm_cascade.jsonl"
    pack = ingest_token_econ_export(fixture_path)
    assert len(pack["tables"]["runs"]) == 2
    assert len(pack["tables"]["routing_log"]) == 2

    ws = ingest_and_build(
        get_preset("frugal_router"),
        seed=42,
        n_sessions=500,
        data_source="token_econ",
        uploaded_tables=pack["tables"],
    )
    assert len(ws.runs) >= 2
    assert hasattr(ws, "routing_log")
    assert len(ws.routing_log) == 2
