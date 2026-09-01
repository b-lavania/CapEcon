"""Value ledger rollup and surplus."""

import pandas as pd

from analytics.agentic_profile import get_preset
from analytics.value_ledger import fill_value_block, rollup_outcome_value, value_sentence
from core.workspace import Workspace, EMPTY_OUTCOMES


def _minimal_ws(outcomes: pd.DataFrame, meta: dict | None = None) -> Workspace:
    profile = get_preset("api_metered")
    return Workspace(
        seed=1,
        profile=profile,
        built_at=pd.Timestamp.utcnow(),
        workspaces=pd.DataFrame([{"workspace_id": "WS-1"}]),
        seats=pd.DataFrame(),
        agents=pd.DataFrame(),
        capabilities=pd.DataFrame([{"capability_id": "CAP-1", "agent_id": "AGT-1"}]),
        capability_versions=pd.DataFrame(),
        runs=pd.DataFrame(
            [{"run_id": "R1", "capability_id": "CAP-1", "success": True, "run_cost_usd": 1.0}]
        ),
        approvals=pd.DataFrame(),
        connector_events=pd.DataFrame(),
        product_events=pd.DataFrame(),
        retention_marks=pd.DataFrame(),
        experiment_assignments=pd.DataFrame(),
        experiment_exposures=pd.DataFrame(),
        experiment_outcomes=pd.DataFrame(),
        outcomes=outcomes,
        meta=meta or {},
    )


def test_rollup_outcome_value_sums_verified():
    outcomes = pd.DataFrame(
        [
            {
                "outcome_id": "O1",
                "account_id": "A1",
                "agent_run_id": "R1",
                "outcome_type": "task_completion",
                "success": True,
                "verified": True,
                "verified_by": "webhook",
                "outcome_value_usd": 10.0,
            },
            {
                "outcome_id": "O2",
                "account_id": "A1",
                "agent_run_id": "R1",
                "outcome_type": "task_completion",
                "success": True,
                "verified": True,
                "verified_by": "webhook",
                "outcome_value_usd": 5.0,
            },
        ]
    )
    ws = _minimal_ws(outcomes)
    assert rollup_outcome_value(ws, capability_id="CAP-1") == 15.0


def test_fill_value_block_observed_and_surplus():
    outcomes = pd.DataFrame(
        [
            {
                "outcome_id": "O1",
                "account_id": "A1",
                "agent_run_id": "R1",
                "outcome_type": "task_completion",
                "success": True,
                "verified": True,
                "verified_by": "webhook",
                "outcome_value_usd": 12.0,
            },
        ]
    )
    ws = _minimal_ws(outcomes)
    econ = fill_value_block(
        {"floor_usd": 2.0, "n_verified": 1},
        workspace=ws,
        profile=ws.profile,
        capability_id="CAP-1",
    )
    assert econ["value_usd"] == 12.0
    assert econ["value_basis"] == "observed"
    assert econ["surplus_usd"] == 10.0
    assert "surplus" in value_sentence(econ)


def test_fill_value_block_prior_from_contract():
    outcomes = EMPTY_OUTCOMES.copy()
    outcomes = pd.concat(
        [
            outcomes,
            pd.DataFrame(
                [
                    {
                        "outcome_id": "O1",
                        "account_id": "A1",
                        "agent_run_id": "R1",
                        "outcome_type": "quote_accepted",
                        "success": True,
                        "verified": True,
                        "verified_by": "webhook",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    meta = {
        "outcome_contract": {
            "outcome_value_map": {"quote_accepted": 8.0},
        }
    }
    ws = _minimal_ws(outcomes, meta=meta)
    econ = fill_value_block(
        {"floor_usd": 1.0, "n_verified": 1},
        workspace=ws,
        profile=ws.profile,
        capability_id="CAP-1",
    )
    assert econ["value_basis"] == "prior"
    assert econ["value_usd"] == 8.0
