"""
Agentic unit economics — token/loop pricing + dual billing-model simulations.

OSS toolkit: models the *builder's* product economics (subscription margin vs
usage revenue), not CapEcon licensing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

_ORACLE_PATH = Path(__file__).parent.parent / "data" / "pricing_oracle.yaml"


def load_pricing_oracle(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _ORACLE_PATH
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def model_prices(oracle: dict[str, Any], model_id: str) -> dict[str, float]:
    models = oracle.get("models", {})
    if model_id not in models:
        model_id = oracle.get("default_model", "gpt-4o")
    m = models.get(model_id, {})
    return {
        "input_cost_per_1k": float(m.get("input_cost_per_1k", 0.005)),
        "output_cost_per_1k": float(m.get("output_cost_per_1k", 0.015)),
        "cached_input_cost_per_1k": float(m.get("cached_input_cost_per_1k", 0.0025)),
    }


def calculate_run_cost(
    runs_df: pd.DataFrame,
    profile: dict[str, Any],
    *,
    pricing_oracle_path: Path | str | None = None,
) -> pd.DataFrame:
    """
    Price each run from tokens + cache credit.

    run_cost_usd ≈ (tokens_in * input + tokens_out * output) / 1000
                   - cache_credit on reused context for steps 2+.
    """
    if runs_df.empty:
        return runs_df.copy()

    out = runs_df.copy()
    oracle = load_pricing_oracle(pricing_oracle_path)
    default_model = profile.get("default_model", oracle.get("default_model", "gpt-4o"))
    cache_hit = float(profile.get("cache_hit_rate", 0.5))

    if "model_id" not in out.columns:
        out["model_id"] = default_model
    out["model_id"] = out["model_id"].fillna(default_model)

    if "tokens_in" not in out.columns:
        steps = out.get("steps_to_completion", pd.Series(1, index=out.index)).fillna(1).clip(lower=1)
        out["tokens_in"] = (steps * 800).astype(int)
        out["tokens_out"] = (steps * 200).astype(int)
    if "steps_to_completion" not in out.columns:
        out["steps_to_completion"] = out.get("loop_count", 1)

    prices = {mid: model_prices(oracle, mid) for mid in out["model_id"].unique()}

    costs = []
    credits = []
    gross = []
    for _, row in out.iterrows():
        p = prices[row["model_id"]]
        tin = float(row["tokens_in"])
        tout = float(row["tokens_out"])
        steps = max(float(row.get("steps_to_completion", 1) or 1), 1.0)
        # Assume steps after the first reuse cache_hit_rate of input tokens at cached rate
        cached_tokens = tin * cache_hit * max(steps - 1, 0) / steps
        fresh_in = tin - cached_tokens
        g = (fresh_in / 1000.0) * p["input_cost_per_1k"]
        g += (cached_tokens / 1000.0) * p["cached_input_cost_per_1k"]
        g += (tout / 1000.0) * p["output_cost_per_1k"]
        # Explicit cache credit vs full-input pricing (for waterfall viz)
        full_in = (tin / 1000.0) * p["input_cost_per_1k"] + (tout / 1000.0) * p["output_cost_per_1k"]
        credit = max(full_in - g, 0.0)
        gross.append(round(full_in, 6))
        credits.append(round(credit, 6))
        costs.append(round(g, 6))

    out["gross_cost_usd"] = gross
    out["cache_credit_usd"] = credits
    out["run_cost_usd"] = costs
    return out


def seat_margins(
    runs_df: pd.DataFrame,
    seats_df: pd.DataFrame,
    profile: dict[str, Any],
) -> pd.DataFrame:
    """
    Dual billing simulation at seat grain.

    b2b_subscription: margin = ARPU - inference COGS
    usage_based: margin = token revenue - inference COGS
    """
    billing = profile.get("billing_model", "b2b_subscription")
    priors = profile.get("priors", {})
    rev_per_1k = float(priors.get("revenue_per_1k_tokens", 0.02))

    if seats_df.empty:
        return pd.DataFrame(
            columns=["seat_id", "billing_model", "revenue_usd", "cogs_usd", "margin_usd", "margin_negative"]
        )

    cost_by_seat = (
        runs_df.groupby("seat_id", as_index=False)["run_cost_usd"].sum()
        if not runs_df.empty and "run_cost_usd" in runs_df.columns
        else pd.DataFrame({"seat_id": [], "run_cost_usd": []})
    )
    tokens_by_seat = pd.DataFrame({"seat_id": [], "tokens": []})
    if not runs_df.empty and "tokens_in" in runs_df.columns:
        tmp = runs_df.copy()
        tmp["tokens"] = tmp["tokens_in"].fillna(0) + tmp.get("tokens_out", 0).fillna(0)
        tokens_by_seat = tmp.groupby("seat_id", as_index=False)["tokens"].sum()

    merged = seats_df[["seat_id", "seat_arpu_monthly"]].merge(cost_by_seat, on="seat_id", how="left")
    merged = merged.merge(tokens_by_seat, on="seat_id", how="left")
    merged["run_cost_usd"] = merged["run_cost_usd"].fillna(0.0)
    merged["tokens"] = merged["tokens"].fillna(0.0)

    if billing == "usage_based":
        merged["revenue_usd"] = merged["tokens"] / 1000.0 * rev_per_1k
    else:
        merged["revenue_usd"] = merged["seat_arpu_monthly"].fillna(0.0)

    merged["cogs_usd"] = merged["run_cost_usd"]
    merged["margin_usd"] = merged["revenue_usd"] - merged["cogs_usd"]
    merged["margin_negative"] = merged["margin_usd"] < 0
    merged["billing_model"] = billing
    return merged[
        ["seat_id", "billing_model", "revenue_usd", "cogs_usd", "margin_usd", "margin_negative"]
    ]


def capability_unit_economics(
    runs_df: pd.DataFrame,
    profile: dict[str, Any],
) -> pd.DataFrame:
    """Per-capability mean cost, loops, and usage-revenue proxy."""
    if runs_df.empty:
        return pd.DataFrame()
    priors = profile.get("priors", {})
    rev_per_1k = float(priors.get("revenue_per_1k_tokens", 0.02))
    billing = profile.get("billing_model", "b2b_subscription")

    cols: dict[str, tuple[str, str]] = {
        "runs": ("run_id", "count"),
        "success_rate": ("success", "mean"),
        "cost_mean": ("run_cost_usd", "mean"),
        "cost_sum": ("run_cost_usd", "sum"),
    }
    if "loop_count" in runs_df.columns:
        cols["loop_mean"] = ("loop_count", "mean")
    if "tokens_in" in runs_df.columns:
        cols["tokens_in_sum"] = ("tokens_in", "sum")
    if "tokens_out" in runs_df.columns:
        cols["tokens_out_sum"] = ("tokens_out", "sum")
    agg = runs_df.groupby("capability_id", as_index=False).agg(**cols)

    tin = agg["tokens_in_sum"] if "tokens_in_sum" in agg.columns else 0
    tout = agg["tokens_out_sum"] if "tokens_out_sum" in agg.columns else 0
    agg["usage_revenue_usd"] = (tin + tout) / 1000.0 * rev_per_1k
    agg["billing_model"] = billing
    if billing == "usage_based":
        agg["unit_margin_usd"] = agg["usage_revenue_usd"] - agg["cost_sum"]
    else:
        thresh = float(priors.get("run_cost_per_success", 0.5))
        agg["unit_margin_usd"] = thresh - agg["cost_mean"]
    return agg
