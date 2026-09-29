"""
Governed metric catalog — single definitions for KPI tiles across pages.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from analytics.conversion import funnel_summary
from analytics.product_metrics import (
    activation_and_ttf_metrics,
    cohort_signups_by_month,
    purchase_dau_over_wau_proxy,
    refund_exposure_rates,
    signup_momentum_latest_vs_prior_month,
)
from core.workspace import Workspace

_LEXICON_PATH = Path(__file__).parent.parent / "metrics" / "lexicon.yaml"


def load_lexicon() -> dict[str, Any]:
    if not _LEXICON_PATH.exists():
        return {"metrics": {}}
    with open(_LEXICON_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"metrics": {}}


def _funnel_cvr(ws: Workspace) -> tuple[float, int, int]:
    summary = funnel_summary(ws.funnel)
    visits = int(summary.loc[summary["step"] == "Visit", "sessions"].iloc[0])
    purchases = int(summary.loc[summary["step"] == "Purchase", "sessions"].iloc[0])
    rate = purchases / visits * 100 if visits else 0.0
    return rate, visits, purchases


def resolve_metric(name: str, workspace: Workspace, *, registry: list | None = None) -> dict[str, Any]:
    """
    Return {name, label, value, display, definition, caveats, meta} for a catalog metric.
    """
    lex = load_lexicon().get("metrics", {})
    spec = lex.get(name, {})
    label = spec.get("label", name)
    caveats = spec.get("caveats", "")
    unit = spec.get("unit", "")

    value: Any = None
    display = "—"
    meta: dict[str, Any] = {}

    if name == "session_to_purchase_cvr":
        rate, visits, purchases = _funnel_cvr(workspace)
        value = rate
        display = f"{rate:.2f}%"
        meta = {"visits": visits, "purchases": purchases}

    elif name == "activated_within_7d":
        act = activation_and_ttf_metrics(workspace.customers, workspace.transactions)
        value = act.get("pct_first_order_within_7d")
        display = f"{value}%" if value is not None else "—"

    elif name == "activated_within_28d":
        act = activation_and_ttf_metrics(workspace.customers, workspace.transactions)
        value = act.get("pct_first_order_within_28d")
        display = f"{value}%" if value is not None else "—"

    elif name == "refund_rate_orders":
        ref = refund_exposure_rates(workspace.transactions)
        value = ref.get("refund_rate_all_orders_pct")
        display = f"{value}%" if value is not None and not pd.isna(value) else "—"

    elif name == "orders_per_active_buyer":
        act = activation_and_ttf_metrics(workspace.customers, workspace.transactions)
        monet = act.get("monetization", {})
        value = monet.get("orders_per_buyer")
        display = f"{value:.3f}" if value is not None else "—"

    elif name == "weekly_purchase_stickiness":
        stick = purchase_dau_over_wau_proxy(workspace.transactions)
        value = stick.get("mean_ratio")
        display = f"{value:.4f}" if value is not None else "—"
        meta = stick

    elif name == "signup_momentum_mom":
        cohorts = cohort_signups_by_month(workspace.customers)
        mom = signup_momentum_latest_vs_prior_month(cohorts)
        value = mom.get("delta_pct")
        display = f"{value:+.2f}%" if value is not None and not pd.isna(value) else "—"
        meta = mom

    elif name == "experiment_active_count":
        reg = registry or []
        value = sum(1 for e in reg if e.get("status") == "active")
        display = str(int(value))

    elif name == "north_star_activation_ratio":
        act = activation_and_ttf_metrics(workspace.customers, workspace.transactions)
        n = act.get("n_customers", 0) or 1
        activated = n - (act.get("pct_never_ordered", 0) / 100 * n)
        value = round(activated / n * 100, 2)
        display = f"{value:.1f}%"
        meta = {"activated_buyers_approx": int(activated), "signups": n}

    elif name == "weekly_delegation_habit":
        seats = workspace.seats
        active = seats[seats["is_activated"]]
        value = active["weekly_delegation"].mean() * 100 if len(active) else 0.0
        display = f"{value:.1f}%"

    elif name == "trust_incident_rate":
        value = workspace.runs["trust_incident"].mean() * 100 if len(workspace.runs) else 0.0
        display = f"{value:.2f}%"

    elif name == "cost_per_successful_run":
        ok = workspace.runs[workspace.runs["success"]]
        value = ok["run_cost_usd"].mean() if len(ok) else 0.0
        display = f"${value:.3f}"

    elif name == "approval_fatigue_index":
        if workspace.approvals.empty:
            value = 0.0
        else:
            value = (workspace.approvals["decision"] == "dismiss").mean()
        display = f"{value:.2f}"

    elif name == "seat_activation_rate":
        value = workspace.seats["is_activated"].mean() * 100
        display = f"{value:.1f}%"

    elif name == "cost_of_leaving_live_usd":
        from analytics.decisions import emit_records
        recs = emit_records(workspace, workspace.profile)
        value = recs[0]["economics"]["primary_metric_usd"] if recs else 0.0
        display = f"${value:,.0f}"

    elif name == "steps_per_successful_task":
        ok = workspace.runs[workspace.runs["success"]] if len(workspace.runs) else workspace.runs
        if len(ok) and "steps_to_completion" in ok.columns:
            value = float(ok["steps_to_completion"].mean())
            display = f"{value:.1f}"
        else:
            value = None
            display = "—"

    elif name == "loop_exhaustion_rate":
        max_loops = float(workspace.profile.get("max_loops_threshold", 8))
        if len(workspace.runs) and "loop_count" in workspace.runs.columns:
            value = (workspace.runs["loop_count"] > max_loops).mean() * 100
            display = f"{value:.1f}%"
        else:
            value = 0.0
            display = "0.0%"

    elif name == "outcome_confirmation_rate":
        ce = workspace.connector_events
        if ce.empty or "outcome_confirmed" not in ce.columns:
            value = None
            display = "—"
        else:
            value = float(ce["outcome_confirmed"].mean() * 100)
            display = f"{value:.1f}%"

    elif name == "eval_score_delta":
        ev = getattr(workspace, "eval_results", None)
        if ev is None or ev.empty:
            value = None
            display = "—"
        else:
            # Mean v2 - v1 delta across capabilities
            deltas = []
            for cap_id, grp in ev.groupby("capability_id"):
                scores = grp.sort_values("capability_version")["score"].tolist()
                if len(scores) >= 2:
                    deltas.append(scores[-1] - scores[0])
            value = float(sum(deltas) / len(deltas) * 100) if deltas else 0.0
            display = f"{value:+.1f}%"

    elif name == "capability_trend_slope":
        from analytics.trend_engine import compute_trends
        trends = compute_trends(workspace.runs) if len(workspace.runs) else {}
        slopes = [t["slope_per_week"] for t in trends.values()]
        value = float(sum(slopes) / len(slopes)) if slopes else 0.0
        display = f"{value:+.3f}"

    elif name == "activation_verified_14d":
        outcomes = getattr(workspace, "outcomes", pd.DataFrame())
        accounts = getattr(workspace, "accounts", workspace.workspaces)
        if outcomes.empty or accounts.empty:
            value = 0.0
        else:
            verified = outcomes[(outcomes["verified"]) & (outcomes["days_since_signup"] <= 14)]
            acc_with = verified["account_id"].nunique()
            value = acc_with / max(len(accounts), 1) * 100
        display = f"{value:.1f}%"

    elif name == "delegation_ratio":
        seats = workspace.seats[workspace.seats["is_activated"]]
        if len(seats):
            value = seats["weekly_delegation"].mean() * 100
        else:
            value = 0.0
        display = f"{value:.1f}%"

    elif name == "autonomy_ratio":
        runs = workspace.runs
        appr = workspace.approvals
        if runs.empty:
            value = 0.0
        else:
            hitl = len(appr) if not appr.empty else 0
            agent_resolved = len(runs) - hitl
            value = agent_resolved / max(len(runs) + hitl, 1) * 100
        display = f"{value:.1f}%"

    elif name == "cost_per_successful_outcome":
        outcomes = getattr(workspace, "outcomes", pd.DataFrame())
        ok_runs = workspace.runs[workspace.runs["success"]]
        if outcomes.empty or ok_runs.empty:
            value = 0.0
        else:
            verified = outcomes[outcomes["verified"] & outcomes["success"]]
            n = max(len(verified), 1)
            value = float(ok_runs["run_cost_usd"].sum() / n)
        display = f"${value:.3f}"

    elif name == "reward_per_dollar":
        runs = workspace.runs
        if runs.empty or "reward" not in runs.columns:
            value = 0.0
            display = "—"
        else:
            cost = float(runs["run_cost_usd"].sum()) if "run_cost_usd" in runs.columns else 0.0
            reward = float(runs["reward"].sum())
            value = reward / cost if cost > 0 else 0.0
            display = f"{value:.2f}"
        meta = {"has_reward": "reward" in runs.columns}

    elif name == "contribution_margin_nrr":
        subs = getattr(workspace, "subscriptions", pd.DataFrame())
        usage = getattr(workspace, "usage_events", pd.DataFrame())
        if subs.empty:
            value = 0.0
        else:
            mrr = subs["mrr_usd"].sum()
            cogs = usage["cost_usd"].sum() if not usage.empty else workspace.runs["run_cost_usd"].sum()
            margin = (mrr - cogs) / max(mrr, 1) * 100
            value = float(margin)
        display = f"{value:.1f}%"

    elif name == "outcome_success_drift":
        outcomes = getattr(workspace, "outcomes", pd.DataFrame())
        if outcomes.empty or "occurred_at" not in outcomes.columns:
            value = 0.0
        else:
            df = outcomes.copy()
            df["week"] = pd.to_datetime(df["occurred_at"]).dt.to_period("W").astype(str)
            weekly = df.groupby("week")["success"].mean()
            if len(weekly) >= 2:
                value = float((weekly.iloc[-1] - weekly.iloc[-2]) * 100)
            else:
                value = 0.0
        display = f"{value:+.1f}%"

    else:
        from analytics import challenge_metrics as cm
        _challenge_map = {
            "power_user_margin_leakage": lambda: (_v := cm.power_user_margin_leakage(workspace), f"${_v[0]:,.0f}", {"margin": _v[0], **_v[1]}),
            "context_utilization_rate": lambda: (cm.context_utilization_rate(workspace), f"{cm.context_utilization_rate(workspace):.1f}%", {}),
            "retry_amplification_factor": lambda: (cm.retry_amplification_factor(workspace), f"{cm.retry_amplification_factor(workspace):.2f}×", {}),
            "unattributed_spend_percentage": lambda: (cm.unattributed_spend_pct(workspace), f"{cm.unattributed_spend_pct(workspace):.1f}%", {}),
            "static_decision_age_median": lambda: (cm.static_decision_age_median(workspace), f"{cm.static_decision_age_median(workspace):.0f}d", {}),
            "time_to_first_production_agent": lambda: (cm.time_to_first_production_agent(workspace), f"{cm.time_to_first_production_agent(workspace):.0f}d", {}),
            "time_to_first_value": lambda: (cm.time_to_first_value_median(workspace), f"{cm.time_to_first_value_median(workspace):.1f}d", {}),
            "paying_but_dormant_rate": lambda: (cm.paying_but_dormant_rate(workspace), f"{cm.paying_but_dormant_rate(workspace):.1f}%", {}),
            "activation_conversion_paid_success": lambda: (cm.activation_conversion_paid_success(workspace), f"{cm.activation_conversion_paid_success(workspace):.1f}%", {}),
            "first_win_definition_coverage": lambda: (cm.first_win_definition_coverage(workspace), f"{cm.first_win_definition_coverage(workspace):.1f}%", {}),
            "integration_depth_score": lambda: (cm.integration_depth_mean(workspace), f"{cm.integration_depth_mean(workspace):.1f}", {}),
            "rebuild_competitor_churn_share": lambda: (cm.rebuild_competitor_churn_share(workspace), f"{cm.rebuild_competitor_churn_share(workspace):.1f}%", {}),
            "context_export_rate": lambda: (cm.context_export_rate(workspace), f"{cm.context_export_rate(workspace):.1f}%", {}),
            "catastrophic_event_rate": lambda: (cm.catastrophic_event_rate(workspace), f"{cm.catastrophic_event_rate(workspace):.2f}/1k", {}),
            "human_intervention_rate": lambda: (cm.human_intervention_rate(workspace), f"{cm.human_intervention_rate(workspace):.1f}%", {}),
            "post_failure_trust_drop": lambda: (cm.post_failure_trust_drop(workspace), f"{cm.post_failure_trust_drop(workspace):+.1f}", {}),
            "verified_outcome_success_rate": lambda: (cm.verified_outcome_success_rate(workspace), f"{cm.verified_outcome_success_rate(workspace):.1f}%", {}),
            "coordination_overhead": lambda: (cm.coordination_overhead_mean(workspace), f"{cm.coordination_overhead_mean(workspace):.1f}%", {}),
            "high_ltv_activation_path_share": lambda: (cm.high_ltv_path_share(workspace), f"{cm.high_ltv_path_share(workspace):.1f}%", {}),
            "agentic_health_score": lambda: (_s := cm.agentic_health_score(workspace), f"{_s[0]:.0f} ({_s[1]})", {"band": _s[1]}),
        }
        if name in _challenge_map:
            value, display, meta = _challenge_map[name]()
        elif name == "handoff_success_rate":
            from analytics.orchestration import handoff_success_rate
            value = handoff_success_rate(workspace)
            display = f"{value:.1f}%"
        elif name == "coordination_cost_ratio":
            from analytics.orchestration import coordination_cost_ratio
            value = coordination_cost_ratio(workspace)
            display = f"{value:.1f}%"
        elif name == "orphaned_subtask_rate":
            from analytics.orchestration import orphaned_subtask_rate
            value = orphaned_subtask_rate(workspace)
            display = f"{value:.1f}%"
        elif name == "trust_boundary_violation_rate":
            from analytics.orchestration import trust_boundary_violations
            value = trust_boundary_violations(workspace)
            display = f"{value:.1f}%"
        elif name not in lex:
            value, display = None, "—"

    definition = spec.get("description") or label
    if spec.get("type") == "ratio":
        definition = f"{label}: purchases / visits (session grain)."

    return {
        "name": name,
        "label": label,
        "value": value,
        "display": display,
        "unit": unit,
        "definition": definition,
        "caveats": caveats,
        "meta": meta,
    }


def resolve_pinned_metrics(
    workspace: Workspace,
    names: list[str] | None = None,
    *,
    registry: list | None = None,
) -> list[dict[str, Any]]:
    """Default executive pins."""
    default_names = names or [
        "weekly_delegation_habit",
        "trust_incident_rate",
        "cost_per_successful_run",
        "seat_activation_rate",
    ]
    return [resolve_metric(n, workspace, registry=registry) for n in default_names]
