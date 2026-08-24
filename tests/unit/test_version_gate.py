"""Version Gate counts API + workspace path."""

from analytics.agentic_profile import get_preset
from analytics.version_gate import evaluate_from_counts, evaluate_version_gate
from core.workspace import build_workspace
from ontology.semantics import load_semantics
from ontology.validate import validate_record


def test_evaluate_from_counts_fail_on_eval():
    r = evaluate_from_counts(n_prev=100, s_prev=80, n_curr=100, s_curr=78, eval_delta=-0.12)
    assert r["ci_status"] == "fail"
    assert r["recommended_action"] in ("hold", "rollback")
    assert r["claim_type"] == "associational"


def test_evaluate_from_counts_pass():
    r = evaluate_from_counts(n_prev=200, s_prev=160, n_curr=200, s_curr=170, eval_delta=0.02)
    assert r["ci_status"] in ("pass", "warn")
    assert "sprt" in r


def test_counts_gate_returns_a_commercial_action_for_ci():
    r = evaluate_from_counts(
        n_prev=200, s_prev=160, n_curr=200, s_curr=170,
        eval_delta=0.02, projected_cpso=1.40, policy_cpso_cap=0.90, list_usd=1.00,
    )
    assert r["price_signal"] == "below_floor"
    assert r["commercial_action"] == "raise_list"
    assert r["commercial_owner_role"] == "finance"
    assert r["floor_usd"] == 1.40 and r["cap_usd"] == 0.90


def test_counts_gate_stays_quiet_without_price_inputs():
    """CI that posts only counts must not receive an invented commercial ask."""
    r = evaluate_from_counts(n_prev=200, s_prev=160, n_curr=200, s_curr=170)
    assert r["price_signal"] == "unpriceable"
    assert r["commercial_action"] is None


def test_counts_gate_internal_budget_never_raises_list():
    r = evaluate_from_counts(
        n_prev=200, s_prev=160, n_curr=200, s_curr=170,
        projected_cpso=22.0, policy_cpso_cap=8.0, baseline_usd=18.40,
        pricing_mode="internal_budget",
    )
    assert r["price_signal"] == "over_baseline"
    assert r["commercial_action"] == "hold_sku"


def test_evaluate_version_gate_emits_claim_type():
    ws = build_workspace(get_preset("assistant_heavy"), seed=42, n_sessions=80)
    gate = evaluate_version_gate(ws)
    assert gate["gdr"]["evidence"]["claim_type"] in ("simulated", "associational", "causal")
    assert gate["ci_status"] in ("pass", "warn", "fail")
    assert "compare" in gate


def test_version_gate_label_comes_from_yaml_not_python():
    """This screen used to hardcode `cost_per_successful_outcome`."""
    ws = build_workspace(get_preset("assistant_heavy"), seed=42, n_sessions=80)
    gate = evaluate_version_gate(
        ws, semantics_overlay={"economics.primary_metric_label": "gate_unit_cost_usd"}
    )
    econ = gate["gdr"]["economics"]
    assert econ["primary_metric_label"] == "gate_unit_cost_usd"
    assert econ["ranking_metric_label"] == "gate_unit_cost_usd"


def test_version_gate_gdr_carries_the_price_block_and_validates():
    ws = build_workspace(get_preset("assistant_heavy"), seed=42, n_sessions=80)
    gate = evaluate_version_gate(ws)
    gdr = gate["gdr"]
    econ = gdr["economics"]
    assert econ["pricing_mode"] == "internal_budget"
    assert "list_usd" not in econ
    assert econ["cost_basis"] in ("simulated", "estimated", "allocated", "metered")
    assert gdr["decision"]["price_signal"] in (
        "unpriceable", "within_policy", "mesh_leak", "below_floor",
        "over_baseline", "flat_bucket_over_cap", "severely_over_cap", "over_cap",
    )
    assert validate_record(gdr, gdr["vertical"]) == []


def test_version_gate_commercial_verb_from_yaml_reaches_the_record():
    """YAML change, no Python change — the promise of the whole layer."""
    ws = build_workspace(get_preset("assistant_heavy"), seed=42, n_sessions=80)
    gate = evaluate_version_gate(
        ws,
        semantics_overlay={
            "decision": {
                "commercial_action_map": {
                    "unpriceable": {"commercial_action": "hold_sku", "rationale": "forced"},
                    "within_policy": {"commercial_action": "hold_sku", "rationale": "forced"},
                }
            }
        },
    )
    decision = gate["gdr"]["decision"]
    if decision["price_signal"] in ("unpriceable", "within_policy"):
        assert decision["commercial_action"] == "hold_sku"
        assert decision["requires_review"] is True
    assert validate_record(gate["gdr"], gate["gdr"]["vertical"]) == []


def test_eval_governance_yaml_declares_a_commercial_map():
    sem = load_semantics("eval_governance")
    cmap = sem["decision"]["commercial_action_map"]
    assert cmap["below_floor"]["commercial_action"] == "raise_list"
    assert cmap["mesh_leak"]["commercial_action"] == "reallocate"
