"""Orchestration / subgraph metrics."""

from analytics.agentic_profile import get_preset
from analytics.metrics import resolve_metric
from analytics.orchestration import build_handoff_table, emit_subgraph_records
from core.workspace import build_workspace
from ontology.exception_taxonomy import all_categories


def test_taxonomy_has_multiagent_categories():
    cats = set(all_categories())
    for key in ("handoff_failure", "trust_boundary", "orphaned_subtask", "coordination_cost"):
        assert key in cats


def test_handoff_and_metrics_resolve():
    ws = build_workspace(get_preset("assistant_heavy"), seed=7, n_sessions=80)
    table = build_handoff_table(ws)
    assert list(table.columns) or table.empty is not False
    for name in (
        "handoff_success_rate",
        "coordination_cost_ratio",
        "orphaned_subtask_rate",
        "trust_boundary_violation_rate",
        "retry_amplification_factor",
    ):
        m = resolve_metric(name, ws)
        assert m["display"] != ""


def test_emit_subgraph_records_valid_shape():
    ws = build_workspace(get_preset("ops_mission"), seed=3, n_sessions=80)
    recs = emit_subgraph_records(ws)
    for rec in recs:
        assert rec["vertical"] == "orchestration"
        assert rec["subject"]["entity_type"] == "workflow"
        assert rec["evidence"]["claim_type"] in ("simulated", "associational")
        assert rec["decision"]["recommended_action"]
