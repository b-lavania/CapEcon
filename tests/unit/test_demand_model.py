"""Demand model wrapper — surplus grid, lazy import, optional pypricing fit."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from analytics.agentic_profile import get_preset
from analytics.demand_model import (
    enrich_economics_from_demand_fit,
    fit_demand,
    pypricing_available,
    surplus_optimal_price,
)
from analytics.demand_panel import build_demand_panel
from core.workspace import build_workspace
from data.ground_truth import get as get_ground_truth


def test_decisions_module_does_not_import_pypricing():
    import analytics.decisions  # noqa: F401

    assert "pypricing" not in sys.modules


def test_surplus_grid_respects_floor():
    panel = pd.DataFrame(
        {
            "sku": ["CAP-1"] * 4,
            "period": ["2025-W01", "2025-W02", "2025-W03", "2025-W04"],
            "price": [0.80, 0.92, 1.00, 1.15],
            "quantity": [10, 12, 8, 6],
        }
    )
    floor = 0.95

    def _predict(df, hdi_prob=0.9):
        prices = df["price"].astype(float)
        q = 100.0 * (prices / prices.mean()) ** -0.8
        return pd.DataFrame({"quantity_mean": q})

    model = SimpleNamespace(predict=_predict, optimize_prices=lambda **kw: pd.DataFrame())
    surplus_opt, _ = surplus_optimal_price(model, "CAP-1", floor, panel)
    assert surplus_opt is not None
    assert surplus_opt >= floor


def test_enrich_economics_from_demand_fit_cache():
    profile = get_preset("api_metered")
    ws = build_workspace(profile, seed=7, n_sessions=50)
    ws.meta = {
        "demand_fit": {
            "underpowered": False,
            "skus": {
                "CAP-003": {"surplus_opt_usd": 1.18, "elasticity_mean": -0.76},
            },
        }
    }
    out = enrich_economics_from_demand_fit({}, ws, "CAP-003")
    assert out["surplus_opt_usd"] == 1.18
    assert out["demand_elasticity_mean"] == -0.76


def test_fit_demand_returns_underpowered_for_assistant_heavy():
    from analytics.demand_panel import build_demand_panel, panel_power

    profile = get_preset("assistant_heavy")
    ws = build_workspace(profile, seed=42, n_sessions=200)
    power = panel_power(build_demand_panel(ws))
    assert not power["ok"]
    result = fit_demand(ws)
    if pypricing_available():
        assert result is not None
        assert result.get("underpowered") is True
    else:
        assert result is None


@pytest.mark.slow
def test_elasticity_recovery_api_metered():
    pytest.importorskip("pypricing")
    profile = get_preset("api_metered")
    ws = build_workspace(profile, seed=42, n_sessions=800)
    panel = build_demand_panel(ws)
    result = fit_demand(ws, panel=panel, draws=150, tune=150, chains=2, seed=42)
    assert result is not None
    assert not result.get("underpowered")
    gt = get_ground_truth(ws.seed)
    planted = float(gt.planted_elasticity)
    treated = set(gt.planted_treated_skus or [])
    hits = []
    for sku, row in (result.get("skus") or {}).items():
        if sku not in treated:
            continue
        eps = row.get("elasticity_mean")
        if eps is not None:
            hits.append(abs(float(eps) - planted) < 0.45)
    assert hits and any(hits)
