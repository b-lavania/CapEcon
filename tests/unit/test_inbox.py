"""Inbox filters."""

from analytics.inbox import filter_inbox, owner_for_record


def test_owner_and_filter():
    rec = {
        "record_id": "gdr_x",
        "exceptions": [{"category": "trust_break", "owner": "founder"}],
        "decision": {"verdict": "destructive", "requires_review": True},
        "economics": {"primary_metric_usd": 10},
        "subject": {"entity_type": "capability", "capability_id": "CAP-1"},
    }
    assert owner_for_record(rec) == "founder"
    items = filter_inbox([rec], owner_role="founder", requires_review=True, verdict="destructive")
    assert len(items) == 1
    assert items[0]["inbox"]["owner_role"] == "founder"
