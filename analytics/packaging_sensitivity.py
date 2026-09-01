"""Packaging sensitivity — teaching demand curves (synthetic elasticity)."""

from __future__ import annotations

import pandas as pd


def margin_curve(floor_usd: float, prices: list[float]) -> pd.DataFrame:
    rows = []
    for p in prices:
        margin = float(p) - float(floor_usd)
        rows.append({"list_usd": float(p), "margin_per_outcome": round(margin, 4)})
    return pd.DataFrame(rows)


def synthetic_demand_curve(
    base_conversion: float,
    ref_price: float,
    elasticity: float,
    prices: list[float],
) -> pd.DataFrame:
    """conversion(p) = base * (p / ref_price) ^ elasticity (elasticity typically negative)."""
    rows = []
    ref = max(float(ref_price), 1e-6)
    base = max(float(base_conversion), 0.0)
    for p in prices:
        conv = base * (float(p) / ref) ** float(elasticity)
        conv = max(0.0, min(1.0, conv))
        rows.append({"list_usd": float(p), "conversion_pct": round(conv * 100, 2)})
    return pd.DataFrame(rows)


def breakeven_volume(fixed_costs_usd: float, margin_per_outcome: float) -> float | None:
    if margin_per_outcome <= 0:
        return None
    return round(float(fixed_costs_usd) / margin_per_outcome, 0)


def implied_wtp_cap(floor_usd: float, target_margin_pct: float) -> float:
    """Floor / (1 - target_margin) — list price that clears target margin."""
    tm = max(0.0, min(0.99, float(target_margin_pct)))
    return round(float(floor_usd) / (1.0 - tm), 4)
