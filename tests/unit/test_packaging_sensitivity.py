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
