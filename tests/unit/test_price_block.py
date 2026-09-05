"""Price block: YAML labels, pricing_mode dialects, floor/risk split."""

from analytics.agentic_profile import get_preset
from analytics.decisions import _price_clinical_exceptions, price_exceptions
from analytics.price_block import (
    display_metric_label,
    fill_price_block,
    format_usd,
    humanize_metric_label,
    price_sentence,
    pricing_mode_for_profile,
    primary_metric_label,
    weakest_cost_basis,
)
from ontology.semantics import load_semantics
from ontology.validate import validate_record


def test_primary_metric_label_reads_dotted_yaml():
    sem = load_semantics("agent_runtime")
    assert primary_metric_label(sem) == "cost_of_leaving_live_usd"
    clinical = load_semantics("clinical_runtime")
    assert primary_metric_label(clinical) == "residual_clinical_risk_usd"
    market = load_semantics("marketplace_commerce")
    assert primary_metric_label(market) == "platform_margin_at_risk_usd"


def test_yaml_overlay_changes_label_without_python_edit():
    sem = load_semantics(
        "agent_runtime",
        overlay={"economics.primary_metric_label": "price_per_verified_outcome_usd"},
    )
    profile = get_preset("assistant_heavy")
    exceptions = [
        {
            "category": "run_cost_blowout",
            "title": "too expensive",
            "impact": {"cost_usd": 12.0},
        }
    ]
    econ = price_exceptions(exceptions, profile, semantics=sem)
    assert econ["primary_metric_label"] == "price_per_verified_outcome_usd"
    assert display_metric_label(econ) == "Price per verified outcome"


def test_nested_overlay_also_sets_label():
    sem = load_semantics(
        "capability_lifecycle",
        overlay={"economics": {"primary_metric_label": "unit_cost_usd"}},
    )
    assert primary_metric_label(sem) == "unit_cost_usd"


def test_humanize_does_not_need_a_lookup_table():
    assert humanize_metric_label("residual_clinical_risk_usd") == "Residual clinical risk"
    assert humanize_metric_label("platform_margin_at_risk_usd") == "Platform margin at risk"
    assert humanize_metric_label("cost_of_leaving_live_usd") == "Cost of leaving live"


def test_pricing_mode_per_preset():
    assert pricing_mode_for_profile(get_preset("assistant_heavy")) == "internal_budget"
    assert pricing_mode_for_profile(get_preset("ops_mission")) == "internal_budget"
    assert pricing_mode_for_profile(get_preset("openmed_v22")) == "internal_budget"
    assert pricing_mode_for_profile(get_preset("api_metered")) == "product_sku"
    assert pricing_mode_for_profile(get_preset("marketplace_agentic")) == "marketplace_take"


def test_internal_budget_omits_list_usd():
    profile = get_preset("assistant_heavy")
    sem = load_semantics("agent_runtime")
    econ = fill_price_block(
        {"primary_metric_usd": 100.0, "primary_metric_label": "cost_of_leaving_live_usd", "currency": "USD"},
        semantics=sem,
        profile=profile,
        n_verified=10,
        production_usd=4.3,
    )
    assert econ["pricing_mode"] == "internal_budget"
    assert "list_usd" not in econ
    assert econ["floor_usd"] == 0.43
    assert econ["baseline_usd"] == 18.4
    assert econ["cap_usd"] == 4.0
    assert econ["margin_usd"] == round(18.4 - 0.43, 4)


def test_product_sku_may_have_list_usd():
    profile = get_preset("api_metered")
    sem = load_semantics("agent_runtime")
    econ = fill_price_block(
        {"primary_metric_usd": 50.0, "currency": "USD"},
        semantics=sem,
        profile=profile,
        n_verified=0,
        production_usd=0,
    )
    assert econ["pricing_mode"] == "product_sku"
    # no verified outcomes → no invented floor or list
    assert "floor_usd" not in econ


def test_refuse_zero_floor_when_nothing_verified():
    profile = get_preset("ops_mission")
    sem = load_semantics("capability_lifecycle")
    econ = fill_price_block(
        {"primary_metric_usd": 10.0, "currency": "USD"},
        semantics=sem,
        profile=profile,
        n_verified=0,
        production_usd=12.0,
    )
    assert "floor_usd" not in econ
    assert "floor unavailable" in price_sentence(econ)


def test_cost_basis_override_beats_workspace_none():
    profile = {"pricing_mode": "internal_budget", "ontology_vertical": "agent_runtime", "priors": {}}
    sem = load_semantics("agent_runtime")
    econ = fill_price_block(
        {"primary_metric_usd": 0.00335, "currency": "USD"},
        semantics=sem,
        profile=profile,
        n_verified=1,
        production_usd=0.00335,
        cost_basis="estimated",
    )
    assert econ["cost_basis"] == "estimated"
    assert "list_usd" not in econ
    assert abs(econ["floor_usd"] - 0.00335) < 1e-4


def test_price_sentence_keeps_sub_cent_floor():
    assert format_usd(0.00335).startswith("$0.003")
    text = price_sentence(
        {
            "pricing_mode": "internal_budget",
            "floor_usd": 0.00335,
            "cost_basis": "estimated",
            "n_verified": 1,
        },
        {"claim_type": "associational"},
    )
    assert "floor $0.00 " not in text
    assert "estimated" in text
    assert "associational" in text


def test_weakest_link_cost_basis():
    assert weakest_cost_basis(["metered", "estimated"]) == "estimated"
    assert weakest_cost_basis(["simulated", "metered"]) == "simulated"


def test_price_sentence_two_dialects():
    internal = {
        "pricing_mode": "internal_budget",
        "floor_usd": 6.1,
        "cost_basis": "estimated",
        "attributed_pct": 61,
        "cap_usd": 4.0,
        "baseline_usd": 18.4,
        "n_verified": 40,
    }
    text = price_sentence(internal, {"claim_type": "associational"})
    assert "floor $6.10" in text
    assert "budget cap $4.00" in text
    assert "human baseline $18.40" in text
    assert "associational" in text
    sku = {
        "pricing_mode": "product_sku",
        "floor_usd": 0.43,
        "cost_basis": "metered",
        "attributed_pct": 82,
        "cap_usd": 0.50,
        "list_usd": 0.99,
        "list_basis": "contracted",
        "n_verified": 1240,
    }
    sku_text = price_sentence(sku, {"claim_type": "associational"})
    assert "list $0.99" in sku_text
    assert "cap $0.50" in sku_text


def test_marketplace_pricer_reads_yaml_and_omits_list():
    from analytics.decisions import _price_marketplace_exceptions

    sem = load_semantics(
        "marketplace_commerce",
        overlay={"economics.primary_metric_label": "take_at_risk_usd"},
    )
    profile = get_preset("marketplace_agentic")
    econ = _price_marketplace_exceptions(
        [{"category": "platform_margin_erosion", "title": "t", "impact": {"cost_usd": 9.0}}],
        semantics=sem,
        profile=profile,
    )
    assert econ["primary_metric_label"] == "take_at_risk_usd"
    assert econ["pricing_mode"] == "marketplace_take"
    assert "list_usd" not in econ
    assert display_metric_label(econ) == "Take at risk"


def test_clinical_pricer_splits_floor_and_risk():
    import pandas as pd

    from core.workspace import Workspace

    profile = get_preset("openmed_v22")
    sem = load_semantics("clinical_runtime")
    cr = pd.DataFrame(
        [
            {
                "clinical_run_id": "c1",
                "run_id": "r1",
                "capability_id": "pii_deidentify",
                "phi_in_logs": True,
                "abstention_rate": 0.2,
                "inference_usd": 2.0,
                "review_labor_usd": 3.0,
            },
            {
                "clinical_run_id": "c2",
                "run_id": "r2",
                "capability_id": "pii_deidentify",
                "phi_in_logs": False,
                "abstention_rate": 0.2,
                "inference_usd": 2.0,
                "review_labor_usd": 3.0,
            },
        ]
    )
    ws = Workspace(
        seed=1,
        profile=profile,
        built_at=pd.Timestamp.utcnow(),
        workspaces=pd.DataFrame([{"workspace_id": "WS-1"}]),
        seats=pd.DataFrame(),
        agents=pd.DataFrame(),
        capabilities=pd.DataFrame([{"capability_id": "pii_deidentify", "agent_id": "AGT-1"}]),
        capability_versions=pd.DataFrame(),
        runs=pd.DataFrame(),
        approvals=pd.DataFrame(),
        connector_events=pd.DataFrame(),
        product_events=pd.DataFrame(),
        retention_marks=pd.DataFrame(),
        experiment_assignments=pd.DataFrame(),
        experiment_exposures=pd.DataFrame(),
        experiment_outcomes=pd.DataFrame(),
        clinical_runs=cr,
        meta={"data_source": "synthetic"},
    )
    exceptions = [
        {
            "category": "phi_leakage",
            "title": "phi",
            "capability_id": "pii_deidentify",
            "impact": {"cost_usd": 10},
        }
    ]
    econ = _price_clinical_exceptions(exceptions, ws, semantics=sem, profile=profile)
    assert econ["primary_metric_label"] == "residual_clinical_risk_usd"
    assert econ["pricing_mode"] == "internal_budget"
    assert "list_usd" not in econ
    labels = {b["label"] for b in econ["breakdown"]}
    assert labels >= {"inference", "review_labor", "expected_harm"}
    assert econ["floor_usd"] == round((2 + 2 + 3 + 3) / 2, 4)
    assert "risk_usd" in econ
    assert econ["primary_metric_usd"] == round(
        econ["breakdown"][0]["amount_usd"]
        + econ["breakdown"][1]["amount_usd"]
        + econ["breakdown"][2]["amount_usd"],
        2,
    )


def test_price_block_import_does_not_load_pypricing():
    import sys

    import analytics.price_block  # noqa: F401

    assert "pypricing" not in sys.modules


def test_clinical_fixture_still_validates():
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "ontology/examples/clinical_phi_leakage.minimal.json"
    record = json.loads(path.read_text())
    assert validate_record(record, "clinical_runtime") == []
    assert "list_usd" not in record["economics"]
    assert record["economics"]["floor_usd"] > 0
    assert record["economics"]["risk_usd"] > 0
