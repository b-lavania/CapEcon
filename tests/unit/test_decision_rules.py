"""Tests for YAML-governed decision rules."""

from __future__ import annotations

import pandas as pd

from analytics.agentic_profile import get_preset
from analytics.decisions import emit_records, propose_action
from core.workspace import Workspace
from ontology.decision_rules import resolve_action, resolve_verdict
from ontology.semantics import load_semantics


def _mini_workspace(profile: dict) -> Workspace:
    """Tiny synthetic workspace so emit tests don't wait on full generators."""
    caps = pd.DataFrame(
        [
            {
                "capability_id": "CAP-HARM",
                "name": "Risky Autopilot",
                "agent_id": "AGT-1",
                "kind": "skill",
                "harm_correlation": True,
            },
            {
                "capability_id": "CAP-LEAK",
                "name": "Leaky Onboard",
                "agent_id": "AGT-1",
                "kind": "template",
                "harm_correlation": False,
            },
        ]
    )
    seats = pd.DataFrame(
        [
            {
                "seat_id": "S1",
                "is_churned": True,
                "seat_arpu_monthly": 50.0,
                "is_activated": True,
                "weekly_delegation": 0.6,
                "signup_date": pd.Timestamp("2025-01-01"),
            },
            {
                "seat_id": "S2",
                "is_churned": True,
                "seat_arpu_monthly": 50.0,
                "is_activated": True,
                "weekly_delegation": 0.4,
                "signup_date": pd.Timestamp("2025-02-01"),
            },
            {
                "seat_id": "S3",
                "is_churned": False,
                "seat_arpu_monthly": 50.0,
                "is_activated": True,
                "weekly_delegation": 0.2,
                "signup_date": pd.Timestamp("2025-03-01"),
            },
        ]
    )
    runs = pd.DataFrame(
        [
            {
                "run_id": f"R{i}",
                "capability_id": "CAP-HARM",
                "seat_id": f"S{(i % 3) + 1}",
                "success": True,
                "trust_incident": False,
                "run_cost_usd": 0.3,
                "loop_count": 2,
                "steps_to_completion": 5,
            }
            for i in range(12)
        ]
        + [
            {
                "run_id": f"L{i}",
                "capability_id": "CAP-LEAK",
                "seat_id": f"S{(i % 3) + 1}",
                "success": i % 5 == 0,  # low success → activation leak
                "trust_incident": False,
                "run_cost_usd": 0.2,
                "loop_count": 2,
                "steps_to_completion": 4,
            }
            for i in range(10)
        ]
    )
    return Workspace(
        seed=1,
        profile=profile,
        built_at=pd.Timestamp.utcnow(),
        workspaces=pd.DataFrame([{"workspace_id": "WS-1"}]),
        seats=seats,
        agents=pd.DataFrame([{"agent_id": "AGT-1", "name": "Demo"}]),
        capabilities=caps,
        capability_versions=pd.DataFrame(
            [
                {"capability_id": "CAP-HARM", "capability_version_id": "CAP-HARM-v1", "version": "v1"},
                {"capability_id": "CAP-LEAK", "capability_version_id": "CAP-LEAK-v1", "version": "v1"},
            ]
        ),
        runs=runs,
        approvals=pd.DataFrame(),
        connector_events=pd.DataFrame(),
        product_events=pd.DataFrame(),
        retention_marks=pd.DataFrame(columns=["seat_id", "horizon_days", "retained"]),
        experiment_assignments=pd.DataFrame(),
        experiment_exposures=pd.DataFrame(),
        experiment_outcomes=pd.DataFrame(),
    )


def test_resolve_verdict_from_yaml_categories():
    sem = load_semantics("capability_lifecycle")
    assert resolve_verdict([], sem) == "healthy"
    assert resolve_verdict([{"category": "capability_harm"}], sem) == "destructive"
    assert resolve_verdict([{"category": "activation_leak"}], sem) == "leaking"
    assert resolve_verdict([{"category": "run_cost_blowout"}], sem) == "uneconomic"
    assert resolve_verdict([{"category": "approval_fatigue"}], sem) == "underpowered"
    assert (
        resolve_verdict(
            [{"category": "approval_fatigue"}, {"category": "quality_drift"}],
            sem,
        )
        == "needs_review"
    )


def test_agent_runtime_destructive_maps_to_rollback():
    """Sample YAML: agent_runtime uses rollback for destructive (not throttle)."""
    sem = load_semantics("agent_runtime")
    decision = resolve_action("destructive", sem)
    assert decision["recommended_action"] == "rollback"
    assert decision["requires_review"] is True


def test_capability_lifecycle_destructive_maps_to_throttle():
    sem = load_semantics("capability_lifecycle")
    decision = resolve_action("destructive", sem)
    assert decision["recommended_action"] == "throttle"


def test_emit_uses_profile_vertical_action_map():
    profile = get_preset("assistant_heavy")  # agent_runtime
    ws = _mini_workspace(profile)
    records = emit_records(ws, ws.profile)
    assert len(records) > 0
    assert all(r["vertical"] == "agent_runtime" for r in records)
    destructive = [r for r in records if r["decision"]["verdict"] == "destructive"]
    assert destructive
    assert destructive[0]["decision"]["recommended_action"] == "rollback"


def test_workspace_crm_uses_lifecycle_throttle():
    profile = get_preset("workspace_crm")  # capability_lifecycle
    ws = _mini_workspace(profile)
    records = emit_records(ws, ws.profile)
    destructive = [r for r in records if r["decision"]["verdict"] == "destructive"]
    assert destructive
    assert destructive[0]["decision"]["recommended_action"] == "throttle"
    assert destructive[0]["vertical"] == "capability_lifecycle"


def test_propose_action_reads_same_yaml():
    sem = load_semantics("agent_runtime")
    fake = {"decision": {"verdict": "destructive"}}
    action, rationale = propose_action(fake, sem)
    assert action == "rollback"
    assert "rollback" in rationale.lower() or "Runtime" in rationale or "harm" in rationale.lower()


def test_emit_internal_budget_has_price_block_no_list():
    profile = get_preset("assistant_heavy")
    ws = _mini_workspace(profile)
    records = emit_records(ws, ws.profile, validate=True)
    assert records
    econ = records[0]["economics"]
    assert econ["pricing_mode"] == "internal_budget"
    assert econ["primary_metric_label"] == "cost_of_leaving_live_usd"
    assert "list_usd" not in econ
    overlay = {"economics.primary_metric_label": "price_per_verified_outcome_usd"}
    relabeled = emit_records(ws, ws.profile, validate=True, semantics_overlay=overlay)
    assert relabeled[0]["economics"]["primary_metric_label"] == "price_per_verified_outcome_usd"
