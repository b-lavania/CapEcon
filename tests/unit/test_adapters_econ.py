"""Market / workflow / rl / macro / abm / finance adapters → Workspace."""

from __future__ import annotations

from pathlib import Path

from analytics.agentic_profile import get_preset
from analytics.marketplace_economics import transaction_cpso
from analytics.metrics import resolve_metric
from core.control_plane import ingest_and_build
from data.adapters.abm import ingest_abm_export
from data.adapters.finance import ingest_finance_export
from data.adapters.macro import ingest_macro_export
from data.adapters.market import ingest_market_export
from data.adapters.rl import ingest_rl_export
from data.adapters.workflow import ingest_workflow_export

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "adapters"


def test_market_fixture_survives_workspace_and_cpso():
    pack = ingest_market_export(FIXTURES / "market" / "sample.jsonl")
    assert len(pack["tables"]["agent_transactions"]) == 3
    assert pack["meta"]["evaluator_id"] == "capecon_market_adapter"
    assert pack["meta"]["claim_type"] == "simulated"

    ws = ingest_and_build(
        get_preset("marketplace_agentic"),
        seed=42,
        n_sessions=500,
        data_source="market",
        uploaded_tables=pack["tables"],
    )
    assert len(ws.agent_transactions) == 3
    assert set(ws.agent_transactions["transaction_id"]) == {"TXN-001", "TXN-002", "TXN-003"}
    cpso = transaction_cpso(ws)
    assert cpso["n_verified"] == 2
    assert cpso["cpso"] > 0


def test_workflow_langgraph_fixture():
    pack = ingest_workflow_export(FIXTURES / "workflow" / "sample.jsonl")
    assert len(pack["tables"]["runs"]) == 2
    assert len(pack["tables"]["spans"]) >= 2
    assert "approvals" in pack["tables"]
    ws = ingest_and_build(
        get_preset("assistant_heavy"),
        seed=42,
        n_sessions=500,
        data_source="workflow",
        uploaded_tables=pack["tables"],
    )
    assert len(ws.runs) >= 2


def test_rl_fixture_reward_per_dollar():
    pack = ingest_rl_export(FIXTURES / "rl" / "sample.jsonl")
    assert "reward" in pack["tables"]["runs"].columns
    ws = ingest_and_build(
        get_preset("assistant_heavy"),
        seed=42,
        n_sessions=500,
        data_source="rl",
        uploaded_tables=pack["tables"],
    )
    metric = resolve_metric("reward_per_dollar", ws)
    assert metric["display"] != "—"
    assert metric["value"] != 0


def test_macro_abm_finance_fixtures_parse():
    macro = ingest_macro_export(FIXTURES / "macro" / "sample.jsonl")
    assert len(macro["tables"]["outcomes"]) == 2
    assert macro["meta"]["claim_type"] == "simulated"

    abm = ingest_abm_export(FIXTURES / "abm" / "sample.jsonl")
    assert len(abm["tables"]["accounts"]) == 2

    fin = ingest_finance_export(FIXTURES / "finance" / "sample.jsonl")
    assert "pnl_usd" in fin["tables"]["outcomes"].columns
    assert "latency_ms" in fin["tables"]["runs"].columns
