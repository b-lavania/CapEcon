"""Vision adapter: two records. Agent API $ must never equal a move invoice."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from data.adapters.vision import (
    attach_quote_predictions,
    cheaper_models_holding_band,
    compose_vision_records,
    headline_quote_records,
    ingest_vision_bakeoff,
    ingest_vision_historic_jobs,
    ingest_vision_pack,
    price_in_band,
    refuse_mixed_units,
)
from ontology.validate import validate_record

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BAKEOFF = FIXTURES / "vision_bakeoff_run.json"
HISTORIC = FIXTURES / "vision_historic_jobs.jsonl"


def test_bakeoff_ingest_drops_item_blobs():
    dirty = json.loads(BAKEOFF.read_text())
    dirty["model_summaries"]["gemini-2.5-flash"]["items"] = [{"notes": "secret prompt text"}]
    dirty["model_summaries"]["gemini-2.5-flash"]["prompt"] = "do not copy"
    slim = ingest_vision_bakeoff(dirty)
    row = slim["model_summaries"]["gemini-2.5-flash"]
    assert "items" not in row
    assert "prompt" not in row
    assert row["cost_usd"] == 0.00335
    assert slim["total_api_cost_usd"] == 0.063029


def test_historic_jobs_map_quality_to_charged_basis():
    quotes = ingest_vision_historic_jobs(HISTORIC)
    by_job = {q["subject"]["job_id"]: q for q in quotes}
    assert by_job["ex_job_1"]["economics"]["charged_usd"] == 656.25
    assert by_job["ex_job_1"]["economics"]["charged_basis"] == "invoiced"
    assert by_job["ex_job_1"]["include_in_headline_metrics"] is True
    assert by_job["ex_job_2"]["economics"]["charged_usd"] == 1791.56
    assert by_job["ex_job_5"]["economics"]["charged_usd"] == 1250.0
    assert by_job["ex_job_5"]["economics"]["charged_basis"] == "reconstructed"
    assert by_job["ex_job_5"]["include_in_headline_metrics"] is False
    assert by_job["ex_job_5"]["outcome"]["actuals_quality"] == "guess"
    headlines = headline_quote_records(quotes)
    assert {h["subject"]["job_id"] for h in headlines} == {"ex_job_1", "ex_job_2"}
    assert all(q.get("outcome", {}).get("price_in_band") is None for q in quotes)


def test_price_in_band_only_with_scored_predictions():
    quotes = ingest_vision_historic_jobs(HISTORIC)
    assert price_in_band(656.25, None, None) is None
    scored = attach_quote_predictions(
        quotes,
        {"ex_job_1": {"price_min_dollars": 600, "price_max_dollars": 700}},
    )
    by_job = {q["subject"]["job_id"]: q for q in scored}
    assert by_job["ex_job_1"]["outcome"]["price_in_band"] is True
    assert by_job["ex_job_2"].get("outcome", {}).get("price_in_band") is None
    miss = attach_quote_predictions(
        quotes,
        {"ex_job_1": {"price_min_dollars": 10, "price_max_dollars": 20}},
    )
    assert miss[0]["outcome"]["price_in_band"] is False


def test_compose_keeps_agent_floor_and_move_invoice_apart():
    pack = ingest_vision_pack(BAKEOFF, HISTORIC)
    agent = pack["agent_gdr"]
    quotes = pack["quote_records"]
    econ = agent["economics"]

    assert econ["cost_basis"] == "estimated"
    assert econ["cost_basis"] != "metered"
    assert econ["pricing_mode"] == "internal_budget"
    assert "list_usd" not in econ
    assert econ["primary_metric_label"] != "total_quote_usd"
    assert econ["floor_usd"] < 1.0
    assert abs(econ["floor_usd"] - 0.00335) < 1e-4
    assert econ["n_verified"] == 1
    # Bakeoff total is six models; floor is the baseline run, not the bakeoff sum.
    assert econ["floor_usd"] < 0.01

    charged = [q["economics"]["charged_usd"] for q in quotes]
    assert min(charged) > 100
    assert 656.25 in charged
    assert all(c != econ["floor_usd"] for c in charged)
    assert all("floor_usd" not in q["economics"] for q in quotes)

    assert pack["reallocate"]["to_model"] == "gemini-2.5-flash-lite"
    assert agent["outputs"]["routing_hint"] == "reallocate"
    assert agent["decision"]["recommended_action"] != "reallocate"
    assert agent["decision"]["commercial_action"] == "reallocate"
    assert agent["evidence"]["claim_type"] == "associational"

    assert validate_record(agent, "agent_runtime") == []
    # Quote records are theta-shaped, not CapEcon GDRs.
    for quote in quotes:
        assert quote["vertical"] == "moving"
        assert quote["record_kind"] == "move_quote"


def test_tables_are_agent_cost_not_move_invoices():
    pack = ingest_vision_pack(BAKEOFF, HISTORIC)
    tables = pack["tables"]
    assert "outcomes" not in tables
    costs = list(tables["usage_events"]["cost_usd"])
    assert max(costs) < 1.0
    assert min(costs) > 0
    assert 656.25 not in costs
    assert set(tables["runs"]["capability_id"]) == {"vision_quote"}


def test_cheaper_holding_band_picks_flash_lite():
    bakeoff = ingest_vision_bakeoff(BAKEOFF)
    found = cheaper_models_holding_band(bakeoff)
    assert found
    assert found[0]["model_name"] == "gemini-2.5-flash-lite"
    assert found[0]["cost_usd"] < bakeoff["model_summaries"]["gemini-2.5-flash"]["cost_usd"]


def test_refuse_mixed_units_catches_invoice_on_agent_list():
    pack = ingest_vision_pack(BAKEOFF, HISTORIC)
    bad = json.loads(json.dumps(pack["agent_gdr"]))
    bad["economics"]["list_usd"] = 656.25
    with pytest.raises(ValueError, match="list_usd"):
        refuse_mixed_units(bad, pack["quote_records"])

    also_bad = json.loads(json.dumps(pack["agent_gdr"]))
    also_bad["economics"]["floor_usd"] = 656.25
    with pytest.raises(ValueError, match="move invoice"):
        refuse_mixed_units(also_bad, pack["quote_records"])


def test_compose_itself_refuses_if_caller_stuffs_list():
    bakeoff = ingest_vision_bakeoff(BAKEOFF)
    quotes = ingest_vision_historic_jobs(HISTORIC)
    pack = compose_vision_records(bakeoff, quotes)
    assert "list_usd" not in pack["agent_gdr"]["economics"]
    assert "move_quote_usd" not in pack["agent_gdr"]["economics"]
