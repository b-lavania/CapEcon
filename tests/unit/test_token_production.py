"""Unit tests for token_production analytics."""

import pandas as pd
import numpy as np

from analytics.agentic_profile import get_preset
from analytics.token_production import (
    cascade_opportunity,
    marginal_outcome_per_token,
    token_bloat_flags,
)
from core.control_plane import build_workspace


def test_marginal_outcome_per_token_empty():
    res = marginal_outcome_per_token(pd.DataFrame())
    assert res == {}


def test_marginal_outcome_per_token_computed():
    rng = np.random.default_rng(42)
    n = 50
    tokens = rng.integers(100, 5000, size=n)
    success = rng.choice([True, False], size=n)
    cost = tokens * 0.00001
    runs = pd.DataFrame(
        {
            "run_id": [f"R-{i}" for i in range(n)],
            "capability_id": ["cap_a"] * n,
            "tokens_in": tokens,
            "success": success,
            "run_cost_usd": cost,
        }
    )
    res = marginal_outcome_per_token(runs)
    assert "cap_a" in res
    assert "mopt" in res["cap_a"]
    assert "saturation" in res["cap_a"]
    assert res["cap_a"]["n"] == n


def test_token_bloat_and_cascade_opportunity():
    ws = build_workspace(get_preset("frugal_router"), seed=42, n_sessions=200)
    flags = token_bloat_flags(ws)
    assert isinstance(flags, pd.DataFrame)

    opp = cascade_opportunity(ws)
    assert "savings_usd" in opp
    assert "candidates" in opp
    assert opp["savings_usd"] >= 0.0
