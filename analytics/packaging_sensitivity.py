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


def archetype_cohort_matrix(
    floor_usd: float,
    seat_arpu_monthly: float,
    outcomes_per_seat_month: float,
    n_deciles: int = 10,
) -> pd.DataFrame:
    """
    Generate a gross margin matrix across account deciles for four pricing archetypes.
    Deciles represent outcome volume distribution (power-law: top decile = 10× median).

    Returns DataFrame with columns:
        decile, outcomes_per_month, seat_based_margin, outcome_based_margin,
        hybrid_margin, sla_margin
    """
    import numpy as np

    decile_multipliers = np.array([0.15, 0.25, 0.40, 0.55, 0.70, 0.90, 1.10, 1.50, 2.20, 4.50])
    rows = []
    for i, mult in enumerate(decile_multipliers):
        n_out = outcomes_per_seat_month * mult
        cost = floor_usd * n_out

        seat_margin = seat_arpu_monthly - cost
        outcome_margin = (floor_usd / (1 - 0.30)) * n_out - cost  # 30% target margin
        hybrid_base = seat_arpu_monthly * 0.4
        hybrid_over = max(0.0, n_out - outcomes_per_seat_month) * (floor_usd / (1 - 0.25))
        hybrid_margin = (hybrid_base + hybrid_over) - cost
        sla_premium = floor_usd * n_out * 0.12  # 12% SLA risk buffer
        sla_margin = outcome_margin + sla_premium - cost * 0.05  # expected rebate

        rows.append(
            {
                "decile": i + 1,
                "outcomes_per_month": round(n_out, 1),
                "seat_based_margin": round(seat_margin, 2),
                "outcome_based_margin": round(outcome_margin, 2),
                "hybrid_margin": round(hybrid_margin, 2),
                "sla_margin": round(sla_margin, 2),
            }
        )
    return pd.DataFrame(rows)


def archetype_summary(
    floor_usd: float,
    seat_arpu: float,
    median_outcomes: float,
    target_margin: float = 0.30,
    sla_buffer: float = 0.12,
) -> dict[str, dict[str, Any]]:
    """
    Single-row summary for each of the four pricing archetypes at median volume.
    Returns dict keyed by archetype name with fields: list_usd, margin_usd, note.
    """
    seat = {
        "list_usd": seat_arpu,
        "margin_usd": round(seat_arpu - floor_usd * median_outcomes, 2),
        "note": "Fixed monthly per seat",
    }
    outcome_list = round(floor_usd / max(1e-4, 1.0 - target_margin), 4)
    outcome = {
        "list_usd": outcome_list,
        "margin_usd": round((outcome_list - floor_usd) * median_outcomes, 2),
        "note": f"Pure outcome @ ${outcome_list:.3f}/outcome",
    }
    hybrid_base = seat_arpu * 0.4
    hybrid_over = outcome_list * 0.8
    hybrid_rev = hybrid_base + max(0.0, median_outcomes - median_outcomes * 0.6) * hybrid_over
    hybrid = {
        "list_usd": hybrid_base,
        "overage_usd": hybrid_over,
        "margin_usd": round(hybrid_rev - floor_usd * median_outcomes, 2),
        "note": f"${hybrid_base:.2f}/mo + ${hybrid_over:.3f}/outcome overage",
    }
    sla_list = outcome_list * (1.0 + sla_buffer)
    sla = {
        "list_usd": round(sla_list, 4),
        "margin_usd": round((sla_list - floor_usd) * median_outcomes, 2),
        "note": f"Outcome + {sla_buffer:.0%} SLA risk premium",
    }
    return {
        "seat_based": seat,
        "outcome_based": outcome,
        "hybrid": hybrid,
        "sla_backed": sla,
    }

