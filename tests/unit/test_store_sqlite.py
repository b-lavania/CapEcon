"""SQLite GDR store + triage."""

from ontology.store import (
    append_record,
    get_triage,
    list_hooks,
    log_hook,
    read_records,
    set_triage,
    upsert_record,
)


def _rec(i: str = "gdr_t_1") -> dict:
    return {
        "record_id": i,
        "vertical": "agent_runtime",
        "schema_version": "1.0.0",
        "evaluated_at": "2026-01-01T00:00:00Z",
        "subject": {"entity_type": "capability", "capability_id": "CAP-001"},
        "exceptions": [],
        "decision": {"verdict": "healthy", "recommended_action": "ship"},
        "evidence": {"claim_type": "simulated"},
    }


def test_upsert_and_read(tmp_path):
    append_record(_rec(), store_dir=tmp_path)
    upsert_record(_rec(), store_dir=tmp_path)
    rows = read_records(store_dir=tmp_path)
    assert len(rows) == 1
    assert rows[0]["record_id"] == "gdr_t_1"
    assert (tmp_path / "agent_runtime.jsonl").exists()
    assert (tmp_path / "capecon.sqlite").exists()


def test_triage_and_hooks(tmp_path):
    upsert_record(_rec("gdr_t_2"), store_dir=tmp_path)
    set_triage("gdr_t_2", status="in_review", assignee="Alex", store_dir=tmp_path)
    tri = get_triage("gdr_t_2", store_dir=tmp_path)
    assert tri["status"] == "in_review"
    log_hook("slack_alert", record_id="gdr_t_2", detail={"ok": True}, store_dir=tmp_path)
    events = list_hooks(store_dir=tmp_path)
    assert events[0]["hook"] == "slack_alert"
