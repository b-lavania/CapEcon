"""Fast tests for case study catalog loading."""

import json
from pathlib import Path

import pytest

from data.case_studies import apply_case_study_to_profile, capability_ids_from_catalog, load_case_study
from analytics.agentic_profile import get_preset


def test_load_openmed_case_study():
    catalog = load_case_study("openmed_v2_2")
    assert catalog["sdk"] == "openmed"
    assert catalog["release"] == "2.2.0"
    assert len(catalog["capabilities"]) == 10
    assert len(catalog["planted_negatives"]) >= 4


def test_apply_case_study_sets_capability_ids():
    profile = apply_case_study_to_profile(get_preset("openmed_v22"))
    ids = profile["priors"]["capability_ids"]
    assert "pii_deidentify" in ids
    assert "concept_grounding" in ids
    assert profile["priors"]["n_capabilities"] == len(ids)


def test_clinical_phi_fixture_validates():
    from ontology.validate import validate_record

    path = Path(__file__).resolve().parents[2] / "ontology/examples/clinical_phi_leakage.minimal.json"
    record = json.loads(path.read_text())
    errors = validate_record(record, "clinical_runtime")
    assert errors == []
    assert "residual_clinical_risk_usd" in json.dumps(record)
    assert "Patient" not in json.dumps(record)
