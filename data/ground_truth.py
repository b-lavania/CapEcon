"""
Planted latents for synthetic warehouse — identifiability lab for rigorous estimators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

# Module-level store keyed by (seed, workspace_id)
_STORE: dict[tuple[int, str], "GroundTruth"] = {}


@dataclass
class GroundTruth:
    """Known DGP parameters for a generated workspace."""

    seed: int
    workspace_id: str = "ALL"
    monthly_churn_base: float = 0.06
    population_churn_rate: float = 0.0
    account_hazard_multipliers: dict[str, float] = field(default_factory=dict)
    version_success_rates: dict[str, float] = field(default_factory=dict)
    version_change_points: dict[str, str] = field(default_factory=dict)
    experiment_id: str = "EXP-CAP-VERSION-001"
    experiment_treatment_effect_success: float = 0.0  # absolute pp on success rate
    experiment_treatment_effect_cost_pct: float = 0.0
    churn_reason_codes: dict[str, str] = field(default_factory=dict)
    planted_take_rate: float = 0.12
    planted_assist_share: float = 0.45
    planted_negative_margin_workflows: list[str] = field(default_factory=list)
    planted_verification_gap_rate: float = 0.0
    planted_eb_global_mean: float = 0.08
    planted_change_point_week: str | None = None
    planted_clinical_negatives: dict[str, str] = field(default_factory=dict)
    planted_outcome_value_mean: float = 0.0
    planted_task_tier_list_usd: dict[str, float] = field(default_factory=dict)
    planted_price_change_week: str | None = None
    planted_conversion_at_price: float = 0.0
    planted_wtp_cap_usd: float = 0.0
    planted_elasticity: float = -0.8
    planted_shock_week: str | None = None
    planted_treated_skus: list[str] = field(default_factory=list)
    planted_base_list_usd: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "workspace_id": self.workspace_id,
            "monthly_churn_base": self.monthly_churn_base,
            "population_churn_rate": self.population_churn_rate,
            "account_hazard_multipliers": dict(self.account_hazard_multipliers),
            "version_success_rates": dict(self.version_success_rates),
            "version_change_points": dict(self.version_change_points),
            "experiment_id": self.experiment_id,
            "experiment_treatment_effect_success": self.experiment_treatment_effect_success,
            "experiment_treatment_effect_cost_pct": self.experiment_treatment_effect_cost_pct,
            "churn_reason_codes": dict(self.churn_reason_codes),
            "planted_take_rate": self.planted_take_rate,
            "planted_assist_share": self.planted_assist_share,
            "planted_negative_margin_workflows": list(self.planted_negative_margin_workflows),
            "planted_verification_gap_rate": self.planted_verification_gap_rate,
            "planted_eb_global_mean": self.planted_eb_global_mean,
            "planted_change_point_week": self.planted_change_point_week,
            "planted_clinical_negatives": dict(self.planted_clinical_negatives),
            "planted_outcome_value_mean": self.planted_outcome_value_mean,
            "planted_task_tier_list_usd": dict(self.planted_task_tier_list_usd),
            "planted_price_change_week": self.planted_price_change_week,
            "planted_conversion_at_price": self.planted_conversion_at_price,
            "planted_wtp_cap_usd": self.planted_wtp_cap_usd,
            "planted_elasticity": self.planted_elasticity,
            "planted_shock_week": self.planted_shock_week,
            "planted_treated_skus": list(self.planted_treated_skus),
            "planted_base_list_usd": dict(self.planted_base_list_usd),
        }


def register(gt: GroundTruth) -> None:
    _STORE[(gt.seed, gt.workspace_id)] = gt


def get(seed: int, workspace_id: str = "ALL") -> GroundTruth | None:
    return _STORE.get((seed, workspace_id)) or _STORE.get((seed, "ALL"))


def clear() -> None:
    _STORE.clear()


def population_churn_from_seats(seats: pd.DataFrame) -> float:
    if seats.empty or "is_churned" not in seats.columns:
        return 0.0
    return float(seats["is_churned"].mean())
