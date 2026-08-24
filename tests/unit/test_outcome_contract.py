"""Outcome contract readiness."""

import pandas as pd

from ontology.outcome_contract import apply_template, default_contract, validate_outcomes


def test_template_and_empty_not_ready():
    c = apply_template("support")
    assert "issue_resolved" in c["outcome_types"]
    report = validate_outcomes(pd.DataFrame(), c)
    assert report["ready"] is False
    assert report["n"] == 0


def test_ready_when_verified():
    c = default_contract()
    df = pd.DataFrame(
        {
            "outcome_id": ["o1", "o2"],
            "agent_run_id": ["r1", "r2"],
            "account_id": ["a1", "a1"],
            "outcome_type": ["quote_sent", "quote_accepted"],
            "success": [True, True],
            "verified": [True, True],
            "verified_by": ["deterministic_stage", "deterministic_stage"],
        }
    )
    report = validate_outcomes(df, c)
    assert report["ready"] is True
    assert report["verified_share"] == 1.0
