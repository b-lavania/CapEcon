"""GDR emit always carries claim_type."""

from analytics.agentic_profile import get_preset
from analytics.decisions import emit_capability_records
from core.workspace import build_workspace


def test_emitted_records_have_claim_type():
    ws = build_workspace(get_preset("assistant_heavy"), seed=42, n_sessions=80)
    recs = emit_capability_records(ws, ws.profile)
    assert recs
    for rec in recs:
        assert rec.get("evidence", {}).get("claim_type") == "simulated"
