"""Unit tests for agency_contract analytics."""

from analytics.agency_contract import compute_agency_surplus, sprt_spot_check_threshold
from analytics.agentic_profile import get_preset
from core.control_plane import build_workspace


def test_agency_surplus_and_deficit():
    ws = build_workspace(get_preset("assistant_heavy"), seed=42, n_sessions=200)

    # With high human baseline -> surplus
    surplus_res = compute_agency_surplus(ws, human_baseline_usd=50.0)
    assert surplus_res["agency_surplus_usd"] > 0
    assert surplus_res["agency_deficit"] is False
    assert surplus_res["verification_cost_usd"] >= 0

    # With near-zero human baseline -> deficit
    deficit_res = compute_agency_surplus(ws, human_baseline_usd=0.001)
    assert deficit_res["agency_deficit"] is True


def test_sprt_spot_check_threshold():
    ws = build_workspace(get_preset("assistant_heavy"), seed=42, n_sessions=200)
    res = sprt_spot_check_threshold(ws)
    assert "spot_check_safe" in res
    assert "n_needed" in res
    assert res["n_needed"] > 0
