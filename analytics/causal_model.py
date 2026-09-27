"""
Causal Model Engine for CapEcon.
================================

A parametric business model that propagates inputs through the full causal chain:

    Acquisition → Churn/Retention → Revenue → Unit Economics → Profitability

Every page in CapEcon reads from this model rather than computing in isolation.
This ensures that changing churn on one page ripples into CLV, payback, and
break-even everywhere.

Usage:
    config = DEFAULT_B2C_ECOMMERCE  # or build your own dict
    model = BusinessModel(config)
    summary = model.compute_summary()
    sensitivity = model.compute_sensitivity("clv")
    cohort_df = model.simulate_cohort(n_months=24)
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


# ──────────────────────────────────────────────────────────
#  Default Templates
# ──────────────────────────────────────────────────────────

DEFAULT_B2C_ECOMMERCE: Dict[str, Any] = {
    "business_type": "B2C eCommerce",
    # Acquisition
    "cohort_size": 5000,
    "cac_organic": 8.0,
    "cac_paid": 35.0,
    "paid_mix": 0.45,  # 45% of customers come from paid
    "channel_mix": {
        "Organic": 0.30,
        "Paid Search": 0.25,
        "Social Media": 0.20,
        "Referral": 0.10,
        "Email": 0.10,
        "Affiliate": 0.05,
    },
    # Retention / churn
    "monthly_churn_rate": 0.08,  # 8% monthly
    "segment_churn_multipliers": {
        "Budget": 1.6,
        "Mid-Range": 1.0,
        "Premium": 0.6,
        "Enterprise": 0.4,
    },
    "segment_weights": {
        "Budget": 0.35,
        "Mid-Range": 0.35,
        "Premium": 0.20,
        "Enterprise": 0.10,
    },
    "subscribe_save_pct": 0.0,  # fraction [0-1]
    "subscriber_churn_reduction": 0.80,  # subscribers churn 80% less
    "reactivation_rate": 0.02,  # 2% of churned come back per month
    # Monetization
    "aov": 65.0,  # average order value
    "purchase_frequency": 1.8,  # orders per active customer per month
    "cogs_pct": 0.40,
    "shipping_cost": 5.0,
    "refund_rate": 0.05,
    "discount_frequency": 0.25,
    "discount_depth": 0.15,  # avg discount when applied
    # Marketplace-specific (only used when business_type == "Marketplace")
    "take_rate": 0.15,
    "buyer_fee_split": 0.40,
    "fixed_fee_per_txn": 0.0,
    "n_sellers": 500,
}

DEFAULT_MARKETPLACE: Dict[str, Any] = {
    **DEFAULT_B2C_ECOMMERCE,
    "business_type": "Marketplace",
    "cohort_size": 10000,
    "monthly_churn_rate": 0.06,
    "aov": 48.0,
    "purchase_frequency": 2.2,
    "cogs_pct": 0.0,  # marketplace doesn't own inventory
    "shipping_cost": 0.0,
    "take_rate": 0.15,
    "buyer_fee_split": 0.40,
    "fixed_fee_per_txn": 0.30,
    "n_sellers": 500,
}

DEFAULT_SAAS: Dict[str, Any] = {
    **DEFAULT_B2C_ECOMMERCE,
    "business_type": "SaaS / Subscription",
    "cohort_size": 2000,
    "monthly_churn_rate": 0.04,
    "aov": 99.0,  # monthly subscription price
    "purchase_frequency": 1.0,  # billed once per month
    "cogs_pct": 0.15,
    "shipping_cost": 0.0,
    "refund_rate": 0.02,
    "discount_frequency": 0.10,
    "discount_depth": 0.20,
    "cac_paid": 120.0,
}

DEFAULT_B2C_APP: Dict[str, Any] = {
    **DEFAULT_B2C_ECOMMERCE,
    "business_type": "B2C App",
    "cohort_size": 50000,
    "monthly_churn_rate": 0.15,
    "aov": 4.99,
    "purchase_frequency": 0.8,
    "cogs_pct": 0.10,
    "shipping_cost": 0.0,
    "refund_rate": 0.08,
    "cac_paid": 3.50,
    "cac_organic": 0.50,
}

TEMPLATES = {
    "B2C eCommerce": DEFAULT_B2C_ECOMMERCE,
    "Marketplace": DEFAULT_MARKETPLACE,
    "SaaS / Subscription": DEFAULT_SAAS,
    "B2C App": DEFAULT_B2C_APP,
}


# ──────────────────────────────────────────────────────────
#  Causal Model
# ──────────────────────────────────────────────────────────

class BusinessModel:
    """Parametric business model that propagates inputs through the causal chain.

    Attributes:
        config: dict of business parameters (see DEFAULT_B2C_ECOMMERCE).
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = dict(config)  # defensive copy

    # ── Derived helpers ──

    @property
    def blended_cac(self) -> float:
        """Weighted average CAC across paid and organic channels."""
        pm = self.config["paid_mix"]
        return pm * self.config["cac_paid"] + (1 - pm) * self.config["cac_organic"]

    @property
    def net_revenue_per_order(self) -> float:
        """Revenue per order after refunds, COGS, shipping, discounts."""
        aov = self.config["aov"]
        refund = self.config["refund_rate"]
        cogs = self.config["cogs_pct"]
        ship = self.config["shipping_cost"]
        disc_freq = self.config["discount_frequency"]
        disc_depth = self.config["discount_depth"]

        effective_revenue = aov * (1 - refund) * (1 - disc_freq * disc_depth)
        cost = aov * cogs + ship
        return effective_revenue - cost

    @property
    def monthly_margin_per_active(self) -> float:
        """Gross margin contribution per active customer per month."""
        return self.net_revenue_per_order * self.config["purchase_frequency"]

    # ── Core simulation ──

    def simulate_cohort(self, n_months: int = 24) -> pd.DataFrame:
        """Simulate a single cohort over *n_months*.

        Returns a DataFrame with one row per month:
            month, active, churned_this_month, reactivated, revenue,
            margin, cumulative_margin, ltv_to_date, cac, ltv_cac_ratio
        """
        cfg = self.config
        n = cfg["cohort_size"]
        base_churn = cfg["monthly_churn_rate"]
        sub_pct = cfg["subscribe_save_pct"]
        sub_reduction = cfg["subscriber_churn_reduction"]
        reactivation = cfg["reactivation_rate"]

        # Effective blended churn accounting for subscribers
        eff_churn = base_churn * (1 - sub_pct * sub_reduction)

        cac = self.blended_cac
        margin_per_active = self.monthly_margin_per_active

        rows = []
        active = float(n)
        cumulative_churned = 0.0
        cumulative_margin = 0.0

        for m in range(n_months + 1):
            if m == 0:
                churned_this = 0.0
                reactivated = 0.0
            else:
                churned_this = active * eff_churn
                reactivated = cumulative_churned * reactivation
                active = active - churned_this + reactivated
                active = max(0, active)
                cumulative_churned += churned_this - reactivated

            revenue = active * self.config["aov"] * self.config["purchase_frequency"]
            margin = active * margin_per_active
            cumulative_margin += margin
            ltv_to_date = cumulative_margin / n if n > 0 else 0

            rows.append({
                "month": m,
                "active": round(active),
                "active_pct": round(active / n * 100, 2) if n > 0 else 0,
                "churned_this_month": round(churned_this),
                "reactivated": round(reactivated),
                "cumulative_churned": round(cumulative_churned),
                "revenue": round(revenue, 2),
                "margin": round(margin, 2),
                "cumulative_margin": round(cumulative_margin, 2),
                "ltv_to_date": round(ltv_to_date, 2),
                "cac": round(cac, 2),
                "ltv_cac_ratio": round(ltv_to_date / cac, 2) if cac > 0 else 0,
            })

        return pd.DataFrame(rows)

    def simulate_cohort_by_segment(self, n_months: int = 24) -> pd.DataFrame:
        """Simulate separate cohorts for each segment.

        Returns a long-form DataFrame with columns:
            segment, month, active, active_pct, ...
        """
        cfg = self.config
        seg_weights = cfg.get("segment_weights", {"All": 1.0})
        seg_churn_mults = cfg.get("segment_churn_multipliers", {"All": 1.0})
        n_total = cfg["cohort_size"]

        all_rows = []
        for seg_name, weight in seg_weights.items():
            seg_config = dict(cfg)
            seg_config["cohort_size"] = int(n_total * weight)
            seg_config["monthly_churn_rate"] = (
                cfg["monthly_churn_rate"] * seg_churn_mults.get(seg_name, 1.0)
            )
            seg_model = BusinessModel(seg_config)
            seg_df = seg_model.simulate_cohort(n_months)
            seg_df["segment"] = seg_name
            all_rows.append(seg_df)

        return pd.concat(all_rows, ignore_index=True)

    # ── Summary metrics ──

    def compute_summary(self) -> Dict[str, Any]:
        """Compute headline metrics for the executive summary."""
        cohort = self.simulate_cohort(n_months=36)
        cac = self.blended_cac
        margin_pm = self.monthly_margin_per_active

        # CLV at 24 months
        clv_24 = cohort.loc[cohort["month"] == 24, "ltv_to_date"].iloc[0]
        # CLV at 36 months (longer horizon)
        clv_36 = cohort.loc[cohort["month"] == 36, "ltv_to_date"].iloc[0]

        # Payback month: first month where cumulative margin per user > CAC
        payback_df = cohort[cohort["ltv_to_date"] >= cac]
        payback_month = int(payback_df["month"].iloc[0]) if len(payback_df) > 0 else None

        # LTV:CAC
        ltv_cac = round(clv_24 / cac, 2) if cac > 0 else float("inf")

        # Monthly churn (effective)
        eff_churn = self.config["monthly_churn_rate"] * (
            1 - self.config["subscribe_save_pct"] * self.config["subscriber_churn_reduction"]
        )
        # Annual churn
        annual_churn = 1 - (1 - eff_churn) ** 12

        # Gross margin per order
        gross_margin_pct = (
            self.net_revenue_per_order / self.config["aov"] * 100
            if self.config["aov"] > 0
            else 0
        )

        # Health score: 0-100 composite
        # Components: LTV:CAC (30%), payback speed (25%), retention (25%), margin (20%)
        ltv_cac_score = min(100, (ltv_cac / 5.0) * 100)  # 5x = perfect
        payback_score = (
            max(0, 100 - (payback_month - 1) * 8) if payback_month else 0
        )  # <3 months = great
        retention_score = max(0, (1 - eff_churn) * 100)  # high retention = high score
        margin_score = min(100, max(0, gross_margin_pct * 2))  # 50% margin = perfect

        health_score = round(
            ltv_cac_score * 0.30
            + payback_score * 0.25
            + retention_score * 0.25
            + margin_score * 0.20
        )

        # M1 retention
        m1_retention = cohort.loc[cohort["month"] == 1, "active_pct"].iloc[0]

        return {
            "clv_24": round(clv_24, 2),
            "clv_36": round(clv_36, 2),
            "cac": round(cac, 2),
            "ltv_cac": ltv_cac,
            "payback_month": payback_month,
            "monthly_churn_eff": round(eff_churn * 100, 2),
            "annual_churn": round(annual_churn * 100, 1),
            "gross_margin_pct": round(gross_margin_pct, 1),
            "margin_per_active_monthly": round(margin_pm, 2),
            "net_revenue_per_order": round(self.net_revenue_per_order, 2),
            "health_score": health_score,
            "m1_retention": m1_retention,
            "cohort_size": self.config["cohort_size"],
            "aov": self.config["aov"],
            "purchase_frequency": self.config["purchase_frequency"],
        }

    # ── Revenue waterfall ──

    def compute_waterfall(self) -> pd.DataFrame:
        """Revenue decomposition per order: Gross → Net after each deduction.

        Returns a DataFrame suitable for a Plotly waterfall chart.
        """
        aov = self.config["aov"]
        cogs = aov * self.config["cogs_pct"]
        shipping = self.config["shipping_cost"]
        refund_loss = aov * self.config["refund_rate"]
        discount_loss = aov * self.config["discount_frequency"] * self.config["discount_depth"]
        cac_amort = self.blended_cac / max(
            1,
            self.config["purchase_frequency"]
            * (1 / self.config["monthly_churn_rate"] if self.config["monthly_churn_rate"] > 0 else 24),
        )

        net_contribution = aov - cogs - shipping - refund_loss - discount_loss - cac_amort

        rows = [
            {"label": "Gross Revenue (AOV)", "amount": round(aov, 2), "type": "absolute"},
            {"label": "COGS", "amount": round(-cogs, 2), "type": "relative"},
            {"label": "Shipping", "amount": round(-shipping, 2), "type": "relative"},
            {"label": "Refunds", "amount": round(-refund_loss, 2), "type": "relative"},
            {"label": "Discounts", "amount": round(-discount_loss, 2), "type": "relative"},
            {"label": "CAC (amortized)", "amount": round(-cac_amort, 2), "type": "relative"},
            {"label": "Net Contribution", "amount": round(net_contribution, 2), "type": "total"},
        ]
        return pd.DataFrame(rows)

    # ── Sensitivity analysis ──

    def compute_sensitivity(
        self,
        output_metric: str = "clv_24",
        delta_pct: float = 0.10,
    ) -> pd.DataFrame:
        """Perturb each input by ±delta_pct and measure impact on *output_metric*.

        Returns a DataFrame sorted by absolute impact:
            input_name, base_value, low_output, high_output, swing, elasticity
        """
        # Inputs to perturb and their display names
        perturbable = {
            "monthly_churn_rate": "Monthly Churn Rate",
            "aov": "Avg Order Value",
            "purchase_frequency": "Purchase Frequency",
            "cogs_pct": "COGS %",
            "refund_rate": "Refund Rate",
            "shipping_cost": "Shipping Cost",
            "discount_frequency": "Discount Frequency",
            "discount_depth": "Discount Depth",
            "cac_paid": "Paid CAC",
            "cac_organic": "Organic CAC",
            "paid_mix": "Paid Channel Mix",
            "subscribe_save_pct": "Subscribe & Save %",
            "reactivation_rate": "Reactivation Rate",
        }

        base_summary = self.compute_summary()
        base_val = base_summary[output_metric]

        rows = []
        for key, display in perturbable.items():
            current = self.config.get(key, 0)
            if current == 0:
                # For zero-valued inputs, perturb by adding delta directly
                low_v = 0
                high_v = delta_pct
            else:
                low_v = current * (1 - delta_pct)
                high_v = current * (1 + delta_pct)

            # Low
            cfg_low = dict(self.config)
            cfg_low[key] = low_v
            low_out = BusinessModel(cfg_low).compute_summary()[output_metric]

            # High
            cfg_high = dict(self.config)
            cfg_high[key] = high_v
            high_out = BusinessModel(cfg_high).compute_summary()[output_metric]

            swing = abs(high_out - low_out)
            # Elasticity: % change in output / % change in input
            if base_val != 0 and current != 0:
                elasticity = round(
                    ((high_out - low_out) / base_val)
                    / (2 * delta_pct),
                    3,
                )
            else:
                elasticity = 0.0

            rows.append({
                "input_name": display,
                "input_key": key,
                "base_value": round(current, 4),
                "low_value": round(low_v, 4),
                "high_value": round(high_v, 4),
                "base_output": round(base_val, 2),
                "low_output": round(low_out, 2),
                "high_output": round(high_out, 2),
                "swing": round(swing, 2),
                "elasticity": elasticity,
            })

        df = pd.DataFrame(rows).sort_values("swing", ascending=False).reset_index(drop=True)
        return df

    # ── CAC ceiling ──

    def cac_ceiling(self, target_ltv_cac: float = 3.0, horizon_months: int = 24) -> float:
        """Max affordable CAC given retention curve and monetization.

        Returns the CAC value at which LTV:CAC equals *target_ltv_cac*.
        """
        cohort = self.simulate_cohort(n_months=horizon_months)
        # LTV is cumulative margin per user at horizon
        cumulative_margin = cohort.loc[cohort["month"] == horizon_months, "cumulative_margin"].iloc[0]
        n = self.config["cohort_size"]
        ltv = cumulative_margin / n if n > 0 else 0
        return round(ltv / target_ltv_cac, 2) if target_ltv_cac > 0 else float("inf")

    # ── What-if: single-variable impact ──

    def what_if(self, key: str, new_value: float) -> Dict[str, Any]:
        """Return summary metrics with a single variable changed."""
        cfg = dict(self.config)
        cfg[key] = new_value
        return BusinessModel(cfg).compute_summary()


def calibrate_churn_from_warehouse(workspace, profile: dict | None = None) -> dict[str, Any]:
    """
    One-way feed: warehouse seats → Beta–Binomial posterior on monthly churn.
    Overrides BusinessModel monthly_churn_rate when rigorous.
    """
    from analytics.evidence import is_rigorous_mode
    from analytics.inference.binomial import beta_binomial_posterior
    from data.ground_truth import get

    profile = profile or getattr(workspace, "profile", {})
    seats = workspace.seats
    if seats.empty or "is_churned" not in seats.columns:
        return {"calibrated": False, "message": "No churn labels on seats."}

    churned = int(seats["is_churned"].sum())
    n = len(seats)
    post = beta_binomial_posterior(churned, n)

    gt = get(getattr(workspace, "seed", 0))
    planted = gt.monthly_churn_base if gt else None

    return {
        "calibrated": True,
        "monthly_churn_rate": post["mean"],
        "ci95": post["ci95"],
        "n": n,
        "planted_base": planted,
        "rigorous": is_rigorous_mode(profile),
        "message": f"Calibrated churn {post['mean']:.1%} from {n} seats (warehouse).",
    }
