"""Packaging sensitivity curve math."""

from analytics.packaging_sensitivity import (
    breakeven_volume,
    implied_wtp_cap,
    margin_curve,
    synthetic_demand_curve,
)


def test_margin_curve_at_floor_is_zero():
    df = margin_curve(1.0, [1.0, 1.5, 2.0])
    assert df.iloc[0]["margin_per_outcome"] == 0.0
    assert df.iloc[1]["margin_per_outcome"] == 0.5


def test_breakeven_volume():
    assert breakeven_volume(1000, 2.0) == 500.0
    assert breakeven_volume(1000, 0) is None


def test_implied_wtp_cap():
    assert implied_wtp_cap(0.50, 0.25) == 0.6667


def test_demand_curve_decreases_with_price_when_elasticity_negative():
    df = synthetic_demand_curve(0.4, 1.0, -0.8, [0.5, 1.0, 2.0])
    assert df.iloc[0]["conversion_pct"] > df.iloc[-1]["conversion_pct"]


def test_archetype_functions():
    from analytics.packaging_sensitivity import archetype_cohort_matrix, archetype_summary

    matrix = archetype_cohort_matrix(floor_usd=0.20, seat_arpu_monthly=50.0, outcomes_per_seat_month=10.0)
    assert len(matrix) == 10
    assert "seat_based_margin" in matrix.columns
    assert "outcome_based_margin" in matrix.columns
    assert "hybrid_margin" in matrix.columns
    assert "sla_margin" in matrix.columns

    summary = archetype_summary(floor_usd=0.20, seat_arpu=50.0, median_outcomes=10.0)
    assert "seat_based" in summary
    assert "outcome_based" in summary
    assert "hybrid" in summary
    assert "sla_backed" in summary
    assert summary["seat_based"]["margin_usd"] == 48.0

