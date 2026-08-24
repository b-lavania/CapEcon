"""Adapter scrubbing and OTel ingest."""

from pathlib import Path

from data.adapters.otel import ingest_otel_export
from data.adapters.scrub import scrub_payload, span_has_content

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "golden_otel.jsonl"


def test_scrub_drops_prompt_keys():
    row = scrub_payload({"prompt": "secret", "tokens_used": 9, "capability_id": "CAP-001"})
    assert "prompt" not in row
    assert row["tokens_used"] == 9
    assert row["scrubbed"] is True
    assert not span_has_content(row)


def test_golden_otel_has_no_content_after_ingest():
    tables = ingest_otel_export(FIXTURE)
    assert not tables["spans"].empty
    assert not tables["runs"].empty
    for rec in tables["spans"].to_dict(orient="records"):
        assert not span_has_content(rec)
        assert rec.get("scrubbed") is True
    assert "prompt" not in tables["spans"].columns
    assert "response" not in tables["spans"].columns
    assert "messages" not in tables["spans"].columns
    assert "gen_ai.prompt" not in tables["spans"].columns
