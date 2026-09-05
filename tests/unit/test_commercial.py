"""Commercial actions: the enum gap, signal precedence, and YAML as price policy."""

from __future__ import annotations

import analytics.commercial as commercial_mod
from analytics.commercial import (
    attach_commercial,
    commercial_sentence,
    resolve_commercial_action,
    resolve_price_signal,
)
from ontology.decision_rules import resolve_action
from ontology.exception_taxonomy import ACTIONS, COMMERCIAL_ACTIONS
from ontology.semantics import load_semantics
from ontology.validate import validate_record


# --- the bug this phase existed to fix -------------------------------------


def test_commercial_verb_in_yaml_is_not_rewritten_to_hold():
    """Before ACTIONS grew, resolve_action silently downgraded these to `hold`."""
    for verb in COMMERCIAL_ACTIONS:
        sem = {"decision": {"action_map": {"uneconomic": {"recommended_action": verb}}}}
        out = resolve_action("uneconomic", sem)
        assert out["recommended_action"] == verb, f"{verb} was rewritten"
        assert out["final_action"] == verb


def test_yaml_cannot_waive_review_on_a_price_change():
    sem = {
        "decision": {
            "action_map": {
                "uneconomic": {"recommended_action": "raise_list", "requires_review": False}
            }
        }
    }
    assert resolve_action("uneconomic", sem)["requires_review"] is True


def test_genuinely_unknown_action_still_falls_back_to_hold():
    sem = {"decision": {"action_map": {"uneconomic": {"recommended_action": "invent_money"}}}}
    assert resolve_action("uneconomic", sem)["recommended_action"] == "hold"


def test_every_commercial_verb_is_selectable_in_the_override_box():
    for verb in COMMERCIAL_ACTIONS:
        assert verb in ACTIONS


# --- signals ---------------------------------------------------------------


def test_no_floor_is_unpriceable_not_within_policy():
    sig = resolve_price_signal({"pricing_mode": "product_sku", "cap_usd": 1.0})
    assert sig["price_signal"] == "unpriceable"


def test_floor_with_no_reference_price_is_unpriceable():
    """A floor on its own proves nothing. churnOS must not claim it is fine."""
    sig = resolve_price_signal({"pricing_mode": "product_sku", "floor_usd": 4.0})
    assert sig["price_signal"] == "unpriceable"


def test_floor_inside_cap_is_within_policy():
    sig = resolve_price_signal(
        {"pricing_mode": "product_sku", "floor_usd": 0.30, "cap_usd": 0.50}
    )
    assert sig["price_signal"] == "within_policy"
    assert resolve_commercial_action(
        {"pricing_mode": "product_sku", "floor_usd": 0.30, "cap_usd": 0.50}
    )["commercial_action"] is None


def test_selling_under_cost_is_below_floor():
    econ = {
        "pricing_mode": "product_sku",
        "floor_usd": 1.40,
        "cap_usd": 0.90,
        "charged_usd": 1.00,
    }
    sig = resolve_price_signal(econ)
    assert sig["price_signal"] == "below_floor"
    assert "0.40" in sig["detail"]


def test_internal_agent_costing_more_than_the_human_is_over_baseline():
    econ = {
        "pricing_mode": "internal_budget",
        "floor_usd": 22.0,
        "cap_usd": 8.0,
        "baseline_usd": 18.40,
    }
    # severe multiple would otherwise fire, so baseline must be checked first
    assert resolve_price_signal(econ)["price_signal"] == "over_baseline"


def test_multiple_of_cap_is_severe():
    econ = {"pricing_mode": "product_sku", "floor_usd": 1.20, "cap_usd": 0.50}
    assert resolve_price_signal(econ)["price_signal"] == "severely_over_cap"


def test_mild_overage_is_over_cap():
    econ = {"pricing_mode": "product_sku", "floor_usd": 0.60, "cap_usd": 0.50}
    assert resolve_price_signal(econ)["price_signal"] == "over_cap"
    assert resolve_commercial_action(econ)["commercial_action"] == "split_tier"


def test_flat_bucket_over_cap_kills_all_inclusive():
    econ = {"pricing_mode": "product_sku", "floor_usd": 0.60, "cap_usd": 0.50}
    out = resolve_commercial_action(econ, profile={"billing_model": "b2b_subscription"})
    assert out["price_signal"] == "flat_bucket_over_cap"
    assert out["commercial_action"] == "kill_all_inclusive"


# --- precedence: routing before repricing ----------------------------------


def test_list_below_demand_opt_before_below_floor():
    econ = {
        "pricing_mode": "product_sku",
        "floor_usd": 0.50,
        "cap_usd": 2.00,
        "charged_usd": 0.80,
        "surplus_opt_usd": 1.20,
    }
    sig = resolve_price_signal(econ)
    assert sig["price_signal"] == "list_below_demand_opt"
    assert resolve_commercial_action(econ)["commercial_action"] == "raise_list"


def test_mesh_leak_outranks_raise_list(monkeypatch):
    """A cheaper route beats a price rise. Never ask finance for a retry bug."""
    monkeypatch.setattr(commercial_mod, "_mesh_leak", lambda ws, th: (True, "retry amplification 6.2x"))
    econ = {
        "pricing_mode": "product_sku",
        "floor_usd": 1.40,
        "cap_usd": 0.90,
        "charged_usd": 1.00,
    }
    out = resolve_commercial_action(econ, workspace=None)
    assert out["price_signal"] == "mesh_leak"
    assert out["commercial_action"] == "reallocate"
    assert out["commercial_owner_role"] == "platform"


def test_mesh_leak_does_not_fire_when_economics_fit(monkeypatch):
    """Retries are only a commercial signal if they push the floor past the cap."""
    called = {"n": 0}

    def _spy(ws, th):
        called["n"] += 1
        return True, "loud"

    monkeypatch.setattr(commercial_mod, "_mesh_leak", _spy)
    econ = {"pricing_mode": "product_sku", "floor_usd": 0.10, "cap_usd": 0.50}
    assert resolve_price_signal(econ)["price_signal"] == "within_policy"
    assert called["n"] == 0


# --- YAML is the price policy ----------------------------------------------


def test_clinical_yaml_never_asks_to_raise_a_list_price():
    """Internal budget has no SKU. The vertical map must route, not reprice."""
    sem = load_semantics("clinical_runtime")
    econ = {
        "pricing_mode": "internal_budget",
        "floor_usd": 9.0,
        "cap_usd": 8.0,
        "baseline_usd": 45.0,
    }
    out = resolve_commercial_action(econ, semantics=sem)
    assert out["commercial_action"] == "reallocate"
    assert out["commercial_action"] != "raise_list"


def test_clinical_lowers_the_severe_threshold_from_yaml():
    """severe_overage_multiple 1.5 in clinical YAML vs 2.0 default."""
    econ = {
        "pricing_mode": "internal_budget",
        "floor_usd": 12.8,
        "cap_usd": 8.0,
        "baseline_usd": 45.0,
    }
    assert resolve_price_signal(econ)["price_signal"] == "over_cap"
    sem = load_semantics("clinical_runtime")
    assert resolve_price_signal(econ, semantics=sem)["price_signal"] == "severely_over_cap"
    assert resolve_commercial_action(econ, semantics=sem)["commercial_action"] == "hold_sku"


def test_marketplace_yaml_cuts_credits_where_sku_would_split_tier():
    econ = {"pricing_mode": "marketplace_take", "floor_usd": 0.60, "cap_usd": 0.50}
    assert resolve_commercial_action(econ)["commercial_action"] == "split_tier"
    sem = load_semantics("marketplace_commerce")
    assert resolve_commercial_action(econ, semantics=sem)["commercial_action"] == "cut_credits"


def test_unknown_verb_in_yaml_is_dropped_not_downgraded():
    sem = {"decision": {"commercial_action_map": {"over_cap": {"commercial_action": "free_money"}}}}
    econ = {"pricing_mode": "product_sku", "floor_usd": 0.60, "cap_usd": 0.50}
    out = resolve_commercial_action(econ, semantics=sem)
    assert out["commercial_action"] is None
    assert "unknown commercial action" in out["commercial_rationale"]


# --- attach + record shape -------------------------------------------------


def test_attach_forces_review_and_names_an_owner():
    decision = {"verdict": "uneconomic", "recommended_action": "hold", "requires_review": False}
    econ = {
        "pricing_mode": "product_sku",
        "floor_usd": 1.40,
        "cap_usd": 0.90,
        "charged_usd": 1.00,
    }
    attach_commercial(decision, econ, semantics=load_semantics("eval_governance"))
    assert decision["commercial_action"] == "raise_list"
    assert decision["commercial_owner_role"] == "finance"
    assert decision["requires_review"] is True
    assert decision["recommended_action"] == "hold"  # ops axis untouched


def test_attach_leaves_a_clean_record_when_unpriceable():
    decision = {"verdict": "healthy", "recommended_action": "ship"}
    attach_commercial(decision, {"pricing_mode": "internal_budget"})
    assert decision["price_signal"] == "unpriceable"
    assert decision["commercial_action"] is None
    assert "requires_review" not in decision


def test_commercial_decision_validates_against_the_schema():
    record = {
        "record_id": "gdr_commercial_0001",
        "vertical": "eval_governance",
        "schema_version": "1.0.0",
        "ontology_version": "eval_governance_v1",
        "evaluated_at": "2026-08-23T12:00:00+00:00",
        "evaluator_id": "test",
        "subject": {"entity_type": "capability", "capability_id": "CAP-1"},
        "exceptions": [],
        "economics": {
            "primary_metric_usd": 12.0,
            "primary_metric_label": "cost_per_successful_outcome_usd",
            "currency": "USD",
            "pricing_mode": "product_sku",
            "floor_usd": 1.40,
            "cap_usd": 0.90,
            "charged_usd": 1.00,
            "cost_basis": "estimated",
        },
        "decision": {"verdict": "uneconomic", "recommended_action": "hold"},
    }
    attach_commercial(record["decision"], record["economics"])
    assert validate_record(record, "eval_governance") == []


def test_sentence_says_who_to_ask():
    econ = {
        "pricing_mode": "product_sku",
        "floor_usd": 1.40,
        "cap_usd": 0.90,
        "charged_usd": 1.00,
    }
    out = resolve_commercial_action(econ, semantics=load_semantics("eval_governance"))
    line = commercial_sentence(out)
    assert line.startswith("raise_list → finance")

    quiet = resolve_commercial_action(
        {"pricing_mode": "product_sku", "floor_usd": 0.1, "cap_usd": 0.5}
    )
    assert "No commercial action" in commercial_sentence(quiet)
