"""
Decision engine: classify → rank → price → emit GrowthDecisionRecords.

Verdicts, actions, and classification thresholds are governed by
ontology/*/semantics.yaml (see ontology/decision_rules.py).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from analytics.commercial import attach_commercial
from analytics.price_block import (
    display_metric_label,
    fill_price_block,
    primary_metric_label,
)
from analytics.value_ledger import fill_value_block, outcome_contract
from analytics.demand_model import enrich_economics_from_demand_fit
from analytics.wtp_priors import apply_wtp_to_price_block, wtp_cap_from_data
from core.workspace import Workspace
from ontology.decision_rules import (
    build_rule_trace,
    get_classification_thresholds,
    get_posterior_thresholds,
    load_rules_for_vertical,
    resolve_action,
    resolve_verdict,
    resolve_verdict_from_posteriors,
)
from ontology.exception_taxonomy import get_category
from ontology.validate import validate_record


def _capability_stats(ws: Workspace) -> pd.DataFrame:
    caps = ws.capabilities.copy()
    runs = ws.runs.copy()
    seats = ws.seats.copy()

    if runs.empty:
        caps["run_count"] = 0
        caps["success_rate"] = 0.0
        caps["trust_rate"] = 0.0
        caps["dismiss_rate"] = 0.0
        caps["harm_score"] = 0.0
        caps["loop_mean"] = 0.0
        caps["steps_mean"] = 0.0
        caps["confirm_rate"] = 1.0
        return caps

    run_agg_spec: dict[str, tuple[str, str]] = {
        "run_count": ("run_id", "count"),
        "success_rate": ("success", "mean"),
        "trust_rate": ("trust_incident", "mean"),
        "run_cost_mean": ("run_cost_usd", "mean"),
    }
    if "loop_count" in runs.columns:
        run_agg_spec["loop_mean"] = ("loop_count", "mean")
    if "steps_to_completion" in runs.columns:
        run_agg_spec["steps_mean"] = ("steps_to_completion", "mean")

    run_agg = runs.groupby("capability_id").agg(**run_agg_spec).reset_index()

    cap_seats = runs.merge(seats[["seat_id", "is_churned", "seat_arpu_monthly"]], on="seat_id")
    churn_by_cap = cap_seats.groupby("capability_id")["is_churned"].mean().reset_index(name="churn_rate")

    merged = caps.merge(run_agg, on="capability_id", how="left").merge(churn_by_cap, on="capability_id", how="left")
    merged = merged.fillna(0)

    if not ws.approvals.empty:
        appr = ws.approvals.merge(runs[["run_id", "capability_id"]], on="run_id")
        dismiss = appr[appr["decision"] == "dismiss"].groupby("capability_id").size()
        total_appr = appr.groupby("capability_id").size()
        merged["dismiss_rate"] = merged["capability_id"].map(
            lambda c: dismiss.get(c, 0) / max(total_appr.get(c, 1), 1)
        )
    else:
        merged["dismiss_rate"] = 0.0

    confirm_rate = {}
    if not ws.connector_events.empty and "outcome_confirmed" in ws.connector_events.columns:
        ce = ws.connector_events.merge(
            runs[["run_id", "capability_id", "success"]].rename(columns={"success": "run_success"}),
            on="run_id",
        )
        ce_ok = ce[ce["run_success"]]
        if not ce_ok.empty:
            confirm_rate = (
                ce_ok.groupby("capability_id")["outcome_confirmed"].mean().to_dict()
            )
    merged["confirm_rate"] = merged["capability_id"].map(lambda c: confirm_rate.get(c, 1.0))

    merged["harm_score"] = merged.apply(
        lambda r: (r.get("harm_correlation", False) or r["churn_rate"] > 0.15) * r["churn_rate"],
        axis=1,
    )
    return merged


def _append_exception(
    exceptions: list[dict[str, Any]],
    *,
    base: dict[str, Any],
    category: str,
    title: str,
    confidence: float,
    rank: int,
    impact_cost: float,
    capability_id: str,
    extra: dict[str, Any] | None = None,
) -> None:
    cat = get_category(category)
    item = {
        **base,
        "exception_id": f"exc_{len(exceptions) + 1:04d}",
        "category": category,
        "title": title,
        "description": cat["playbook_hint"],
        "confidence": confidence,
        "rank": rank,
        "severity": cat["default_severity"],
        "owner": cat["owner_role"],
        "impact": {"cost_usd": float(impact_cost)},
        "capability_id": capability_id,
    }
    if extra:
        item.update(extra)
    exceptions.append(item)


def _append_account_exception(
    exceptions: list[dict[str, Any]],
    *,
    base: dict[str, Any],
    category: str,
    title: str,
    confidence: float,
    rank: int,
    impact_cost: float,
    account_id: str,
) -> None:
    cat = get_category(category)
    exceptions.append({
        **base,
        "exception_id": f"exc_acc_{len(exceptions) + 1:04d}",
        "category": category,
        "title": title,
        "description": cat["playbook_hint"],
        "confidence": confidence,
        "rank": rank,
        "severity": cat["default_severity"],
        "owner": cat["owner_role"],
        "impact": {"cost_usd": float(impact_cost)},
        "account_id": account_id,
    })


def classify(workspace: Workspace, profile: dict[str, Any], *, semantics_overlay: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return raw exception candidates per capability using YAML thresholds."""
    from analytics.trend_engine import compute_trends

    vertical = profile.get("ontology_vertical", "capability_lifecycle")
    semantics = load_rules_for_vertical(vertical, overlay=semantics_overlay)
    thresh = get_classification_thresholds(semantics, profile)
    priors = thresh.get("_priors", {})
    arpu = float(priors.get("seat_arpu_monthly", 50))

    stats = _capability_stats(workspace)
    trends = compute_trends(workspace.runs) if "steps_to_completion" in workspace.runs.columns else {}
    exceptions: list[dict[str, Any]] = []

    dead = thresh.get("capability_dead", {})
    act = thresh.get("activation_leak", {})
    harm = thresh.get("capability_harm", {})
    fatigue = thresh.get("approval_fatigue", {})
    trust = thresh.get("trust_break", {})
    cost = thresh.get("run_cost_blowout", {})
    loops = thresh.get("loop_exhaustion", {})
    drift = thresh.get("quality_drift", {})
    confirm = thresh.get("outcome_confirmation_gap", {})

    for _, cap in stats.iterrows():
        cap_id = cap["capability_id"]
        base = {
            "blocked_entity": {"entity_type": "capability", "entity_id": cap_id},
            "blocks_subject": True,
        }

        max_runs = int(dead.get("max_run_count_exclusive", 5))
        if cap["run_count"] < max_runs:
            _append_exception(
                exceptions,
                base=base,
                category="capability_dead",
                title=f"{cap['name']} has near-zero adoption",
                confidence=0.85,
                rank=99,
                impact_cost=arpu * 10,
                capability_id=cap_id,
            )
            continue

        act_mult = float(act.get("success_rate_prior_multiplier", 0.6))
        if cap["success_rate"] < priors.get("activation_rate", 0.5) * act_mult:
            _append_exception(
                exceptions,
                base=base,
                category="activation_leak",
                title=f"{cap['name']} activation leak",
                confidence=0.7,
                rank=1,
                impact_cost=cap["run_count"] * arpu * 0.1,
                capability_id=cap_id,
            )

        harm_min = float(harm.get("harm_score_min", 0.08))
        check_corr = bool(harm.get("check_harm_correlation", True))
        harm_score = cap["harm_score"]
        from analytics.evidence import is_rigorous_mode
        if is_rigorous_mode(profile):
            from analytics.inference.empirical_bayes import capability_harm_eb_one
            eb = capability_harm_eb_one(workspace, cap_id)
            harm_score = eb.get("shrunk_rate", harm_score)
        if harm_score > harm_min or (check_corr and cap.get("harm_correlation", False)):
            harm_extra: dict[str, Any] = {}
            from analytics.evidence import is_rigorous_mode, pack_evidence
            from analytics.causal_uplift import estimate_uplift

            if is_rigorous_mode(profile):
                uplift = estimate_uplift(workspace)
                ct = uplift.get("claim_type", "associational")
                eb = capability_harm_eb_one(workspace, cap_id)
                harm_extra["evidence"] = pack_evidence(
                    model_id="empirical_bayes_beta_binomial_v0",
                    claim_type=ct,
                    estimand="harm_rate_shrunk",
                    posterior_mean=eb.get("shrunk_rate", harm_score),
                    ci95=[
                        max(0, eb.get("shrunk_rate", harm_score) - 0.05),
                        min(1, eb.get("shrunk_rate", harm_score) + 0.05),
                    ],
                    n=eb.get("n", 0),
                    experiment_id=uplift.get("experiment_id"),
                )
                harm_extra["evidence"]["raw_rate"] = eb.get("raw_rate", cap["harm_score"])
                harm_extra["evidence"]["caption"] = (
                    f"raw {eb.get('raw_rate', cap['harm_score']):.1%} → shrunk {eb.get('shrunk_rate', harm_score):.1%}"
                )
            _append_exception(
                exceptions,
                base=base,
                category="capability_harm",
                title=f"{cap['name']} correlates with churn",
                confidence=0.72,
                rank=1,
                impact_cost=cap["churn_rate"] * cap["run_count"] * arpu * 6,
                capability_id=cap_id,
                extra=harm_extra or None,
            )

        fatigue_mult = float(fatigue.get("dismiss_rate_prior_multiplier", 1.0))
        if cap["dismiss_rate"] > priors.get("approval_fatigue_rate", 0.2) * fatigue_mult:
            _append_exception(
                exceptions,
                base=base,
                category="approval_fatigue",
                title=f"{cap['name']} approval fatigue",
                confidence=0.65,
                rank=2,
                impact_cost=cap["run_count"] * 2,
                capability_id=cap_id,
            )

        trust_mult = float(trust.get("trust_rate_prior_multiplier", 1.5))
        if cap["trust_rate"] > priors.get("trust_incident_rate", 0.04) * trust_mult:
            _append_exception(
                exceptions,
                base=base,
                category="trust_break",
                title=f"{cap['name']} trust incidents elevated",
                confidence=0.8,
                rank=1,
                impact_cost=cap["trust_rate"] * cap["run_count"] * 100,
                capability_id=cap_id,
            )

        cost_mult = float(cost.get("run_cost_prior_multiplier", 2.0))
        if cap["run_cost_mean"] > priors.get("run_cost_per_success", 0.5) * cost_mult:
            _append_exception(
                exceptions,
                base=base,
                category="run_cost_blowout",
                title=f"{cap['name']} run economics broken",
                confidence=0.75,
                rank=2,
                impact_cost=cap["run_cost_mean"] * cap["run_count"],
                capability_id=cap_id,
            )

        max_loops = float(loops.get("max_loops", profile.get("max_loops_threshold", 8)))
        if cap.get("loop_mean", 0) > max_loops:
            _append_exception(
                exceptions,
                base=base,
                category="loop_exhaustion",
                title=f"{cap['name']} exceeds loop budget",
                confidence=0.78,
                rank=1,
                impact_cost=cap["run_cost_mean"] * cap["run_count"] * 0.5,
                capability_id=cap_id,
            )

        trend = trends.get(cap_id, {})
        min_slope = float(drift.get("min_slope_per_week", 0.05))
        if trend.get("direction") == "worsening" and float(trend.get("slope_per_week", 0)) > min_slope:
            _append_exception(
                exceptions,
                base=base,
                category="quality_drift",
                title=f"{cap['name']} steps-to-completion drifting up",
                confidence=0.68,
                rank=2,
                impact_cost=cap["run_count"] * arpu * 0.05,
                capability_id=cap_id,
                extra={"trend": trend},
            )

        max_confirm = float(confirm.get("max_confirm_rate", 0.55))
        min_success = float(confirm.get("min_success_rate", 0.5))
        if cap.get("confirm_rate", 1.0) < max_confirm and cap["success_rate"] > min_success:
            _append_exception(
                exceptions,
                base=base,
                category="outcome_confirmation_gap",
                title=f"{cap['name']} succeeds without confirmed downstream writes",
                confidence=0.66,
                rank=3,
                impact_cost=cap["run_count"] * 3,
                capability_id=cap_id,
            )

        seat_cols = workspace.seats.columns
        if {"is_activated", "signup_date", "weekly_delegation"}.issubset(seat_cols):
            cap_seat_runs = workspace.runs[workspace.runs["capability_id"] == cap_id]
            if len(cap_seat_runs) >= 10:
                cap_seats = workspace.seats[
                    workspace.seats["seat_id"].isin(cap_seat_runs["seat_id"])
                    & workspace.seats["is_activated"]
                ]
                if len(cap_seats) >= 5:
                    q33 = cap_seats["signup_date"].quantile(0.33)
                    q67 = cap_seats["signup_date"].quantile(0.67)
                    early = cap_seats[cap_seats["signup_date"] <= q33]
                    late = cap_seats[cap_seats["signup_date"] >= q67]
                    early_del = early["weekly_delegation"].mean() if len(early) else 0.0
                    late_del = late["weekly_delegation"].mean() if len(late) else 0.0
                    if early_del > 0.35 and late_del < early_del * 0.6:
                        _append_exception(
                            exceptions,
                            base=base,
                            category="habit_collapse",
                            title=f"{cap['name']} delegation habit collapsing",
                            confidence=0.7,
                            rank=2,
                            impact_cost=cap["run_count"] * arpu * 0.08,
                            capability_id=cap_id,
                        )

    from analytics.evidence import is_rigorous_mode
    if is_rigorous_mode(profile):
        from analytics.drift import outcome_distribution_drift
        from analytics.evidence import pack_evidence

        od = outcome_distribution_drift(workspace)
        js_thresh = float(thresh.get("outcome_mix_drift", {}).get("js_min", 0.08))
        if od.get("js", 0) >= js_thresh:
            _append_exception(
                exceptions,
                base={"workspace_id": workspace.workspaces["workspace_id"].iloc[0] if len(workspace.workspaces) else "WS-0000"},
                category="outcome_mix_drift",
                title="Outcome mix shifted vs prior window",
                confidence=0.7,
                rank=2,
                impact_cost=arpu * 20,
                capability_id=stats.iloc[0]["capability_id"] if len(stats) else "CAP-001",
                extra={
                    "evidence": pack_evidence(
                        model_id="js_divergence_v0",
                        claim_type="associational",
                        estimand="outcome_mix_js",
                        posterior_mean=od["js"],
                        ci95=[max(0, od["js"] - 0.02), od["js"] + 0.02],
                        n=od.get("baseline", [0.5, 0.5])[0] * 1000,
                    ),
                    "drift": od,
                },
            )

    graph = getattr(workspace, "connector_capability_graph", None)
    frag = thresh.get("connector_fragility", {})
    min_fail = float(frag.get("min_fail_rate", 0.25))
    min_blast = int(frag.get("min_blast_radius_seats", 5))
    if graph is not None and not graph.empty:
        for _, row in graph.iterrows():
            fail_rate = row["fail_count"] / max(row["call_count"], 1)
            blast = int(row.get("blast_radius_seats", 0))
            if fail_rate > min_fail and blast >= min_blast:
                cap_id = row["capability_id"]
                conn_id = row["connector_id"]
                cat = get_category("connector_fragility")
                exceptions.append({
                    "exception_id": f"exc_{len(exceptions) + 1:04d}",
                    "category": "connector_fragility",
                    "title": f"Connector {conn_id} fragile for {cap_id}",
                    "description": cat["playbook_hint"],
                    "confidence": 0.74,
                    "rank": 2,
                    "severity": cat["default_severity"],
                    "owner": cat["owner_role"],
                    "blocks_subject": True,
                    "blocked_entity": {"entity_type": "capability", "entity_id": cap_id},
                    "impact": {"cost_usd": float(fail_rate * blast * arpu)},
                    "capability_id": cap_id,
                    "connector_id": conn_id,
                })

    ev = getattr(workspace, "eval_results", None)
    eval_thresh = thresh.get("eval_regression", {})
    min_delta = float(eval_thresh.get("min_delta_pct", -10))
    if ev is not None and not ev.empty:
        for cap_id, grp in ev.groupby("capability_id"):
            scores = grp.sort_values("capability_version")["score"].tolist()
            if len(scores) >= 2:
                delta_pct = (scores[-1] - scores[0]) / max(scores[0], 0.01) * 100
                if delta_pct < min_delta:
                    _append_exception(
                        exceptions,
                        base={
                            "blocked_entity": {"entity_type": "capability", "entity_id": cap_id},
                            "blocks_subject": True,
                        },
                        category="eval_regression",
                        title=f"{cap_id} eval regression {delta_pct:.0f}%",
                        confidence=0.82,
                        rank=1,
                        impact_cost=arpu * 20,
                        capability_id=cap_id,
                    )

    # margin_leakage: top token seats with negative margin
    if not workspace.runs.empty and not workspace.seats.empty:
        seat_cost = workspace.runs.groupby("seat_id")["run_cost_usd"].sum()
        for seat_id, cost in seat_cost.nlargest(max(1, len(seat_cost) // 20)).items():
            row = workspace.seats[workspace.seats["seat_id"] == seat_id]
            if row.empty:
                continue
            rev = float(row["seat_arpu_monthly"].iloc[0]) * 6
            if cost > rev * 1.2:
                cap_runs = workspace.runs[workspace.runs["seat_id"] == seat_id]
                cap_id = cap_runs["capability_id"].mode().iloc[0] if len(cap_runs) else "CAP-000"
                _append_exception(
                    exceptions,
                    base={"blocked_entity": {"entity_type": "capability", "entity_id": cap_id}, "blocks_subject": True},
                    category="margin_leakage",
                    title=f"Power-user margin leakage on {seat_id}",
                    confidence=0.76,
                    rank=2,
                    impact_cost=float(cost - rev),
                    capability_id=cap_id,
                )

    cat = getattr(workspace, "catastrophic_events", pd.DataFrame())
    if not cat.empty and not workspace.runs.empty:
        for _, ev in cat.head(5).iterrows():
            cap_id = workspace.runs.loc[workspace.runs["run_id"] == ev["run_id"], "capability_id"]
            cap_id = cap_id.iloc[0] if len(cap_id) else "CAP-000"
            _append_exception(
                exceptions,
                base={"blocked_entity": {"entity_type": "capability", "entity_id": cap_id}, "blocks_subject": True},
                category="catastrophic_failure",
                title=ev.get("description", "Catastrophic agent action"),
                confidence=0.9,
                rank=1,
                impact_cost=arpu * 50,
                capability_id=cap_id,
            )

    return exceptions


def classify_accounts(workspace: Workspace, profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Account-subject exception candidates (retention / churn codes)."""
    priors = profile.get("priors", {})
    arpu = float(priors.get("seat_arpu_monthly", 59.0))
    accounts = getattr(workspace, "accounts", workspace.workspaces)
    outcomes = getattr(workspace, "outcomes", pd.DataFrame())
    seats = workspace.seats
    runs = workspace.runs
    exceptions: list[dict[str, Any]] = []

    for _, acc in accounts.iterrows():
        acc_id = acc["account_id"]
        base = {
            "blocked_entity": {"entity_type": "account", "entity_id": acc_id},
            "blocks_subject": True,
        }
        acc_seats = seats[seats["workspace_id"] == acc_id]
        if acc_seats.empty:
            continue
        n_seats = len(acc_seats)
        churn_rate = acc_seats["is_churned"].mean()
        ltv_risk = churn_rate * acc_seats["seat_arpu_monthly"].sum() * 6

        acc_outcomes = outcomes[outcomes["account_id"] == acc_id] if not outcomes.empty else pd.DataFrame()
        verified_14d = False
        if not acc_outcomes.empty:
            verified_14d = bool(((acc_outcomes["verified"]) & (acc_outcomes["days_since_signup"] <= 14)).any())

        activated = acc_seats["is_activated"].mean() > 0.3
        delegation = acc_seats[acc_seats["is_activated"]]["weekly_delegation"].mean() if activated else 0.0
        acc_runs = runs[runs["seat_id"].isin(acc_seats["seat_id"])]
        success_rate = acc_runs["success"].mean() if len(acc_runs) else 0.0
        cost_per_outcome = 0.0
        if len(acc_runs) and not acc_outcomes.empty:
            ok_outcomes = acc_outcomes[acc_outcomes["success"] & acc_outcomes["verified"]]
            n_ok = max(len(ok_outcomes), 1)
            cost_per_outcome = float(acc_runs["run_cost_usd"].sum() / n_ok)

        if activated and not verified_14d:
            _append_account_exception(
                exceptions, base=base, category="tourist",
                title=f"Account {acc_id} — no verified outcome ≤14d",
                confidence=0.81, rank=1, impact_cost=ltv_risk * 0.5, account_id=acc_id,
            )
            if acc.get("is_paying", True):
                _append_account_exception(
                    exceptions, base=base, category="activation_failure",
                    title=f"Account {acc_id} — paying with zero verified outcomes (14d)",
                    confidence=0.84, rank=1, impact_cost=ltv_risk * 0.65, account_id=acc_id,
                )
        if delegation < priors.get("weekly_habit_rate", 0.45) * 0.55 and success_rate < priors.get("activation_rate", 0.5) * 0.7:
            _append_account_exception(
                exceptions, base=base, category="value_failure",
                title=f"Account {acc_id} — value failure pattern",
                confidence=0.73, rank=1, impact_cost=ltv_risk * 0.7, account_id=acc_id,
            )
        if delegation < priors.get("weekly_habit_rate", 0.45) * 0.6 and success_rate >= priors.get("activation_rate", 0.5) * 0.8:
            _append_account_exception(
                exceptions, base=base, category="efficiency",
                title=f"Account {acc_id} — delegation down, success stable",
                confidence=0.68, rank=2, impact_cost=ltv_risk * 0.4, account_id=acc_id,
            )
        plan_threshold = arpu * n_seats / 40
        if cost_per_outcome > plan_threshold and cost_per_outcome > 0:
            _append_account_exception(
                exceptions, base=base, category="price",
                title=f"Account {acc_id} — $/outcome above plan",
                confidence=0.71, rank=2, impact_cost=cost_per_outcome * 10, account_id=acc_id,
            )
        if churn_rate > float(priors.get("monthly_churn_base", 0.06)) * 1.5:
            _append_account_exception(
                exceptions, base=base, category="displacement",
                title=f"Account {acc_id} — elevated churn",
                confidence=0.65, rank=3, impact_cost=ltv_risk, account_id=acc_id,
            )
        churned_seats = acc_seats[acc_seats["is_churned"]]
        active_seats = acc_seats[~acc_seats["is_churned"]]
        if len(churned_seats) and len(active_seats) and len(churned_seats) / n_seats > 0.2:
            _append_account_exception(
                exceptions, base=base, category="champion_departure",
                title=f"Account {acc_id} — champion seat churned",
                confidence=0.69, rank=2,
                impact_cost=float(churned_seats["seat_arpu_monthly"].sum() * 6),
                account_id=acc_id,
            )
        if activated and delegation < 0.25 and not verified_14d:
            _append_account_exception(
                exceptions, base=base, category="product_gap",
                title=f"Account {acc_id} — activation without habit",
                confidence=0.67, rank=3, impact_cost=arpu * n_seats * 0.3, account_id=acc_id,
            )

    return exceptions


def rank_exceptions(exceptions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank by impact cost descending."""
    def sort_key(e: dict) -> float:
        return -(e.get("impact", {}).get("cost_usd", 0))

    ranked = sorted(exceptions, key=sort_key)
    for i, e in enumerate(ranked, start=1):
        e["rank"] = i
    return ranked


def _finalize_economics(
    economics: dict[str, Any],
    *,
    semantics: dict[str, Any] | None,
    profile: dict[str, Any] | None,
    workspace: Workspace | None = None,
    capability_id: str | None = None,
    account_id: str | None = None,
    production_usd: float | None = None,
    risk_usd: float | None = None,
    n_verified: int | None = None,
    cost_basis: str | None = None,
) -> dict[str, Any]:
    economics = fill_price_block(
        economics,
        semantics=semantics,
        profile=profile,
        workspace=workspace,
        capability_id=capability_id,
        account_id=account_id,
        production_usd=production_usd,
        risk_usd=risk_usd,
        n_verified=n_verified,
        cost_basis=cost_basis,
    )
    economics = fill_value_block(
        economics,
        workspace=workspace,
        profile=profile,
        capability_id=capability_id,
        account_id=account_id,
    )
    economics = enrich_economics_from_demand_fit(economics, workspace, capability_id)
    if workspace is not None and (profile or {}).get("priors", {}).get("math_mode") == "rigorous":
        wtp = wtp_cap_from_data(workspace, profile)
        economics = apply_wtp_to_price_block(
            economics, wtp, profile, workspace=workspace, capability_id=capability_id,
        )
    return economics


def price_exceptions(
    exceptions: list[dict[str, Any]],
    profile: dict[str, Any],
    *,
    semantics: dict[str, Any] | None = None,
    workspace: Workspace | None = None,
    capability_id: str | None = None,
    account_id: str | None = None,
) -> dict[str, Any]:
    total = sum(e.get("impact", {}).get("cost_usd", 0) for e in exceptions)
    breakdown = [
        {"label": e["category"], "amount_usd": e.get("impact", {}).get("cost_usd", 0), "notes": e.get("title", "")}
        for e in exceptions[:5]
    ]
    if semantics is None:
        vertical = profile.get("ontology_vertical", "capability_lifecycle")
        semantics = load_rules_for_vertical(vertical)
    economics = {
        "primary_metric_usd": round(total, 2),
        "primary_metric_label": primary_metric_label(semantics),
        "currency": "USD",
        "breakdown": breakdown,
    }
    return _finalize_economics(
        economics,
        semantics=semantics,
        profile=profile,
        workspace=workspace,
        capability_id=capability_id,
        account_id=account_id,
    )


def _emit_subject_records(
    workspace: Workspace,
    profile: dict[str, Any],
    raw: list[dict[str, Any]],
    *,
    entity_type: str,
    group_key: str,
    validate: bool,
    semantics_overlay: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    vertical = profile.get("ontology_vertical", "capability_lifecycle")
    ontology_version = profile.get("ontology_version", f"{vertical}_v1")
    semantics = load_rules_for_vertical(vertical, overlay=semantics_overlay)
    ws_id = workspace.workspaces["workspace_id"].iloc[0] if len(workspace.workspaces) else "WS-0000"

    by_subject: dict[str, list[dict]] = {}
    for e in raw:
        key = e.get(group_key)
        if key:
            by_subject.setdefault(key, []).append(e)

    records: list[dict[str, Any]] = []
    rec_idx = 0
    caps = workspace.capabilities.set_index("capability_id")
    versions = workspace.capability_versions.groupby("capability_id")["capability_version_id"].last()

    for subject_id, excs in by_subject.items():
        rec_idx += 1
        ranked = rank_exceptions(excs)
        cap_id = subject_id if entity_type == "capability" else None
        acc_id = subject_id if entity_type == "account" else None
        economics = price_exceptions(
            ranked,
            profile,
            semantics=semantics,
            workspace=workspace,
            capability_id=cap_id,
            account_id=acc_id,
        )
        verdict = resolve_verdict(ranked, semantics)
        decision = resolve_action(verdict, semantics)

        record_stub: dict[str, Any] = {
            "exceptions": ranked,
            "economics": economics,
        }
        if entity_type == "account":
            from analytics.evidence import is_rigorous_mode
            from analytics.account_risk import account_risk_detail

            if is_rigorous_mode(profile):
                detail = account_risk_detail(workspace, subject_id, profile)
                record_stub["p_churn_30d"] = detail.get("p_churn_30d")
                record_stub["evidence"] = detail.get("evidence")

        pt = get_posterior_thresholds(semantics)
        if semantics.get("classification", {}).get("posterior_thresholds") or profile.get("priors", {}).get("math_mode") == "rigorous":
            override = resolve_verdict_from_posteriors(record_stub, pt)
            if override and override != verdict:
                verdict = override
                decision = resolve_action(verdict, semantics)
                decision["rationale"] = (
                    f"Posterior threshold override → {verdict}. " + decision["rationale"]
                )

        decision["rule_trace"] = build_rule_trace(ranked, semantics, verdict, decision)
        attach_commercial(
            decision, economics, semantics=semantics, workspace=workspace, profile=profile
        )
        cost_name = display_metric_label(economics)
        decision["rationale"] = (
            f"{decision['rationale']} Ranked {len(ranked)} exception(s); "
            f"headline {cost_name} ${economics['primary_metric_usd']:,.0f}."
        )
        src = (workspace.meta or {}).get("data_source", "synthetic")
        claim = "simulated" if src in ("synthetic", None, "") else "associational"

        if entity_type == "capability":
            cap_row = caps.loc[subject_id] if subject_id in caps.index else None
            agent_id = cap_row["agent_id"] if cap_row is not None else "AGT-000"
            subject = {
                "workspace_id": ws_id,
                "entity_type": "capability",
                "capability_id": subject_id,
                "capability_version": versions.get(subject_id, f"{subject_id}-v1"),
                "agent_id": agent_id,
            }
            strip_keys = ("capability_id", "connector_id")
        else:
            subject = {"workspace_id": ws_id, "entity_type": "account", "account_id": subject_id}
            strip_keys = ("account_id",)

        contract = outcome_contract(workspace)
        tier = contract.get("task_tier")
        if tier:
            subject["task_tier"] = tier

        record = {
            "record_id": f"gdr_{entity_type[:3]}_{rec_idx:04d}",
            "vertical": vertical,
            "schema_version": "1.0.0",
            "ontology_version": ontology_version,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "evaluator_id": "churnos_emitter",
            "subject": subject,
            "exceptions": [{k: v for k, v in e.items() if k not in strip_keys} for e in ranked],
            "economics": economics,
            "decision": decision,
        }
        if record_stub.get("p_churn_30d") is not None:
            record["p_churn_30d"] = record_stub["p_churn_30d"]
        evidence = dict(record_stub.get("evidence") or {})
        if subject.get("experiment_id"):
            claim = "causal"
        evidence.setdefault("claim_type", claim)
        record["evidence"] = evidence
        from ui.viz.viz_receipts import attach_viz_receipt

        attach_viz_receipt(record, workspace)
        if validate:
            errors = validate_record(record, vertical)
            if errors:
                raise ValueError(f"Invalid GrowthDecisionRecord {record['record_id']}: {errors}")
        records.append(record)

    records.sort(key=lambda r: -r["economics"]["primary_metric_usd"])
    return records


def emit_capability_records(
    workspace: Workspace,
    profile: dict[str, Any],
    *,
    filter_categories: set[str] | None = None,
    validate: bool = True,
    semantics_overlay: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    raw = classify(workspace, profile, semantics_overlay=semantics_overlay)
    if filter_categories:
        raw = [e for e in raw if e["category"] in filter_categories]
    return _emit_subject_records(
        workspace, profile, raw, entity_type="capability", group_key="capability_id", validate=validate,
        semantics_overlay=semantics_overlay,
    )


def emit_account_records(
    workspace: Workspace,
    profile: dict[str, Any],
    *,
    filter_categories: set[str] | None = None,
    validate: bool = True,
    semantics_overlay: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    raw = classify_accounts(workspace, profile)
    if filter_categories:
        raw = [e for e in raw if e["category"] in filter_categories]
    return _emit_subject_records(
        workspace, profile, raw, entity_type="account", group_key="account_id", validate=validate,
        semantics_overlay=semantics_overlay,
    )


def emit_records(
    workspace: Workspace,
    profile: dict[str, Any],
    *,
    filter_categories: set[str] | None = None,
    validate: bool = True,
    include_accounts: bool = False,
    entity_type: str | None = None,
    semantics_overlay: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Emit GDRs; default capability-only unless include_accounts or entity_type set."""
    if entity_type == "account":
        return emit_account_records(
            workspace, profile, filter_categories=filter_categories, validate=validate,
            semantics_overlay=semantics_overlay,
        )
    if entity_type == "capability":
        return emit_capability_records(
            workspace, profile, filter_categories=filter_categories, validate=validate,
            semantics_overlay=semantics_overlay,
        )

    cap_recs = emit_capability_records(
        workspace, profile, filter_categories=filter_categories, validate=validate,
        semantics_overlay=semantics_overlay,
    )
    if include_accounts:
        acc_recs = emit_account_records(
            workspace, profile, filter_categories=filter_categories, validate=validate,
            semantics_overlay=semantics_overlay,
        )
        merged = acc_recs + cap_recs
        merged.sort(key=lambda r: -r["economics"]["primary_metric_usd"])
        return merged
    return cap_recs


def classify_marketplace(
    workspace: Workspace,
    profile: dict[str, Any],
    *,
    semantics_overlay: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Classify marketplace workflow/seller exceptions."""
    from analytics.marketplace_economics import agent_gmv_attribution, seller_margin_table, workflow_unit_economics

    txn = getattr(workspace, "agent_transactions", pd.DataFrame())
    if txn.empty:
        return []

    vertical = profile.get("ontology_vertical", "marketplace_commerce")
    semantics = load_rules_for_vertical(vertical, overlay=semantics_overlay)
    thresh = get_classification_thresholds(semantics, profile)
    exceptions: list[dict[str, Any]] = []
    base = {"workspace_id": workspace.workspaces["workspace_id"].iloc[0] if len(workspace.workspaces) else "WS-0000"}

    assisted = txn[txn["agent_assist_type"] != "none"]
    manual = txn[txn["agent_assist_type"] == "none"]
    if not assisted.empty and not manual.empty:
        a_margin = (
            assisted["platform_revenue_usd"].sum() - assisted["agent_inference_cost_usd"].sum()
        ) / max(assisted["gmv_usd"].sum(), 1)
        m_margin = (
            manual["platform_revenue_usd"].sum() - manual["agent_inference_cost_usd"].sum()
        ) / max(manual["gmv_usd"].sum(), 1)
        gap_min = float(thresh.get("platform_margin_erosion", {}).get("margin_gap_min", 0.15))
        if a_margin < m_margin - gap_min:
            for cap_id in assisted["capability_id"].dropna().unique():
                we = workflow_unit_economics(workspace, str(cap_id))
                exceptions.append({
                    **base,
                    "category": "platform_margin_erosion",
                    "title": f"Workflow {cap_id} — assisted margin below manual",
                    "confidence": 0.75,
                    "rank": 1,
                    "impact": {"cost_usd": max(0, -we["net_margin"])},
                    "capability_id": str(cap_id),
                    "seller_id": None,
                })

    attr = agent_gmv_attribution(workspace)
    if not attr.empty:
        total_gmv = attr["gmv_usd"].sum()
        max_share = float(thresh.get("agent_gmv_concentration", {}).get("max_share", 0.40))
        top = attr.loc[attr["gmv_usd"].idxmax()]
        if total_gmv > 0 and top["gmv_usd"] / total_gmv > max_share:
            exceptions.append({
                **base,
                "category": "agent_gmv_concentration",
                "title": f"GMV concentration in {top['assist_type']}",
                "confidence": 0.7,
                "rank": 2,
                "impact": {"cost_usd": float(top["gmv_usd"] * 0.1)},
                "capability_id": str(top["capability_id"]),
            })

    verify_min = float(thresh.get("transaction_verification_gap", {}).get("min_verify_rate", 0.55))
    gap_txn = assisted[assisted["success"]]
    if not gap_txn.empty:
        vr = float(gap_txn["verified"].mean())
        if vr < verify_min:
            exceptions.append({
                **base,
                "category": "transaction_verification_gap",
                "title": "Low verification rate on assisted successes",
                "confidence": 0.72,
                "rank": 2,
                "impact": {"cost_usd": float(gap_txn["gmv_usd"].sum() * 0.05)},
                "capability_id": str(gap_txn["capability_id"].mode().iloc[0]) if "capability_id" in gap_txn.columns else "CAP-001",
            })

    blow_min = float(thresh.get("inference_cost_blowout", {}).get("inference_over_take_min", 1.0))
    for cap_id in assisted["capability_id"].dropna().unique():
        we = workflow_unit_economics(workspace, str(cap_id))
        if we["take_per_txn"] > 0 and we["cpso"] / we["take_per_txn"] > blow_min:
            exceptions.append({
                **base,
                "category": "inference_cost_blowout",
                "title": f"Workflow {cap_id} — inference exceeds take",
                "confidence": 0.8,
                "rank": 1,
                "impact": {"cost_usd": max(0, -we["net_margin"])},
                "capability_id": str(cap_id),
            })

    if profile.get("ontology_vertical") == "agentic_commerce" and not assisted.empty:
        slip_max = float(thresh.get("negotiation_slippage", {}).get("max_discount_rate", 0.20))
        squeeze_min = float(thresh.get("take_rate_squeeze", {}).get("min_net_margin_pct", 0.02))
        spread_max = float(thresh.get("bid_ask_spread_anomaly", {}).get("max_spread_to_gmv_ratio", 0.40))
        infra_max = float(thresh.get("inference_over_take", {}).get("max_inference_take_ratio", 0.50))
        for cap_id, grp in assisted.groupby("capability_id"):
            cap_s = str(cap_id)
            gmv = float(grp["gmv_usd"].sum()) if "gmv_usd" in grp.columns else 0.0
            take = float(grp["platform_revenue_usd"].sum()) if "platform_revenue_usd" in grp.columns else 0.0
            inference = (
                float(grp["agent_inference_cost_usd"].sum())
                if "agent_inference_cost_usd" in grp.columns
                else 0.0
            )

            if "negotiation_discount" in grp.columns and grp["negotiation_discount"].notna().any():
                mean_disc = float(grp["negotiation_discount"].dropna().mean())
                if mean_disc > slip_max:
                    exceptions.append({
                        **base,
                        "category": "negotiation_slippage",
                        "title": f"Workflow {cap_s} — negotiation discount above policy",
                        "confidence": 0.75,
                        "rank": 1,
                        "impact": {"cost_usd": max(0.0, gmv * mean_disc)},
                        "capability_id": cap_s,
                    })

            if gmv > 0 and "platform_revenue_usd" in grp.columns and "agent_inference_cost_usd" in grp.columns:
                net = (take - inference) / max(gmv, 1.0)
                if net < squeeze_min:
                    exceptions.append({
                        **base,
                        "category": "take_rate_squeeze",
                        "title": f"Workflow {cap_s} — net margin after inference below floor",
                        "confidence": 0.75,
                        "rank": 1,
                        "impact": {"cost_usd": max(0.0, -net) * gmv},
                        "capability_id": cap_s,
                    })

            if (
                "bid_ask_spread_usd" in grp.columns
                and "gmv_usd" in grp.columns
                and grp["bid_ask_spread_usd"].notna().any()
            ):
                spread_sum = float(grp["bid_ask_spread_usd"].fillna(0).sum())
                spread_ratio = spread_sum / max(gmv, 1.0)
                if spread_ratio > spread_max:
                    exceptions.append({
                        **base,
                        "category": "bid_ask_spread_anomaly",
                        "title": f"Workflow {cap_s} — bid-ask spread vs GMV above policy",
                        "confidence": 0.75,
                        "rank": 1,
                        "impact": {"cost_usd": spread_sum},
                        "capability_id": cap_s,
                    })

            if take > 0 and inference / take > infra_max:
                exceptions.append({
                    **base,
                    "category": "inference_over_take",
                    "title": f"Workflow {cap_s} — inference exceeds share of take",
                    "confidence": 0.75,
                    "rank": 1,
                    "impact": {"cost_usd": inference},
                    "capability_id": cap_s,
                })

    sellers = seller_margin_table(workspace)
    if not sellers.empty:
        worst = sellers.sort_values("net_margin").head(3)
        for _, row in worst.iterrows():
            if row["net_margin"] < 0:
                exceptions.append({
                    **base,
                    "category": "platform_margin_erosion",
                    "title": f"Seller {row['seller_id']} — negative platform margin",
                    "confidence": 0.74,
                    "rank": 2,
                    "impact": {"cost_usd": abs(float(row["net_margin"]))},
                    "seller_id": str(row["seller_id"]),
                    "capability_id": None,
                })

    from analytics.evidence import is_rigorous_mode, pack_evidence
    if is_rigorous_mode(profile):
        from analytics.drift import outcome_distribution_drift
        from analytics.token_risk import daily_spend_series, token_cost_var

        od = outcome_distribution_drift(workspace)
        js_min = float(thresh.get("outcome_mix_drift", {}).get("js_min", 0.08))
        if od.get("js", 0) >= js_min:
            exceptions.append({
                **base,
                "category": "outcome_mix_drift",
                "title": "Outcome mix drift on marketplace runs",
                "confidence": 0.68,
                "rank": 3,
                "impact": {"cost_usd": float(assisted["gmv_usd"].sum() * 0.02) if not assisted.empty else 0},
                "capability_id": str(assisted["capability_id"].mode().iloc[0]) if not assisted.empty else "CAP-001",
                "evidence": pack_evidence(
                    model_id="js_divergence_v0",
                    claim_type="associational",
                    estimand="outcome_mix_js",
                    posterior_mean=od["js"],
                    ci95=[max(0, od["js"] - 0.02), od["js"] + 0.02],
                    n=len(assisted),
                ),
            })
        daily = daily_spend_series(workspace)
        if not daily.empty:
            var = token_cost_var(daily)
            for exc in exceptions:
                if exc.get("category") == "inference_cost_blowout":
                    exc.setdefault("evidence", pack_evidence(
                        model_id="token_var_bootstrap_v0",
                        claim_type="simulated",
                        estimand="daily_spend_var_5pct",
                        posterior_mean=var["var"],
                        ci95=[var["cvar"], var["var"]],
                        n=len(daily),
                    ))

    return exceptions


def _normalize_exceptions(exceptions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure schema-required exception fields are present."""
    out: list[dict[str, Any]] = []
    for i, e in enumerate(exceptions):
        cat = get_category(e["category"])
        item = dict(e)
        item.setdefault("exception_id", f"exc_{i + 1:04d}")
        item.setdefault("description", cat["playbook_hint"])
        item.setdefault("severity", cat["default_severity"])
        item.setdefault("owner", cat["owner_role"])
        if "impact" not in item and "impact_cost" in item:
            item["impact"] = {"cost_usd": float(item.pop("impact_cost"))}
        out.append(item)
    return out


def _price_marketplace_exceptions(
    exceptions: list[dict[str, Any]],
    *,
    semantics: dict[str, Any],
    profile: dict[str, Any],
    workspace: Workspace | None = None,
    capability_id: str | None = None,
    seller_id: str | None = None,
) -> dict[str, Any]:
    total = sum(e.get("impact", {}).get("cost_usd", 0) for e in exceptions)
    breakdown = [
        {"label": e["category"], "amount_usd": e.get("impact", {}).get("cost_usd", 0), "notes": e.get("title", "")}
        for e in exceptions[:5]
    ]
    economics = {
        "primary_metric_usd": round(total, 2),
        "primary_metric_label": primary_metric_label(semantics, "platform_margin_at_risk_usd"),
        "currency": "USD",
        "breakdown": breakdown,
    }
    return _finalize_economics(
        economics,
        semantics=semantics,
        profile=profile,
        workspace=workspace,
        capability_id=capability_id,
        account_id=seller_id,
    )


def emit_marketplace_records(
    workspace: Workspace,
    profile: dict[str, Any],
    *,
    entity_type: str = "workflow",
    validate: bool = True,
    semantics_overlay: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    raw = classify_marketplace(workspace, profile, semantics_overlay=semantics_overlay)
    vertical = profile.get("ontology_vertical", "marketplace_commerce")
    ontology_version = profile.get("ontology_version", f"{vertical}_v1")
    semantics = load_rules_for_vertical(vertical, overlay=semantics_overlay)
    ws_id = workspace.workspaces["workspace_id"].iloc[0] if len(workspace.workspaces) else "WS-0000"

    group_key = "capability_id" if entity_type == "workflow" else "seller_id"
    by_subject: dict[str, list[dict]] = {}
    for e in raw:
        key = e.get(group_key)
        if key:
            by_subject.setdefault(str(key), []).append(e)

    records: list[dict[str, Any]] = []
    for rec_idx, (subject_id, excs) in enumerate(by_subject.items(), start=1):
        ranked = rank_exceptions(_normalize_exceptions(excs))
        cap_id = subject_id if entity_type == "workflow" else None
        seller_id = subject_id if entity_type == "seller" else None
        economics = _price_marketplace_exceptions(
            ranked,
            semantics=semantics,
            profile=profile,
            workspace=workspace,
            capability_id=cap_id,
            seller_id=seller_id,
        )
        verdict = resolve_verdict(ranked, semantics)
        decision = resolve_action(verdict, semantics)
        decision["rule_trace"] = build_rule_trace(ranked, semantics, verdict, decision)
        attach_commercial(
            decision, economics, semantics=semantics, workspace=workspace, profile=profile
        )

        if entity_type == "workflow":
            assist = next((e.get("title", "") for e in ranked), "")
            subject = {
                "workspace_id": ws_id,
                "entity_type": "workflow",
                "capability_id": subject_id,
                "assist_type": assist.split("—")[0].strip() if "—" in assist else "agent_assist",
            }
            strip_keys = ("capability_id", "seller_id")
            prefix = "wfl"
        else:
            subject = {"workspace_id": ws_id, "entity_type": "seller", "seller_id": subject_id}
            strip_keys = ("capability_id", "seller_id")
            prefix = "sel"

        record = {
            "record_id": f"gdr_{prefix}_{rec_idx:04d}",
            "vertical": vertical,
            "schema_version": "1.0.0",
            "ontology_version": ontology_version,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "evaluator_id": "churnos_emitter",
            "subject": subject,
            "exceptions": [{k: v for k, v in e.items() if k not in strip_keys} for e in ranked],
            "economics": economics,
            "decision": decision,
        }
        if validate:
            errors = validate_record(record, vertical)
            if errors:
                raise ValueError(f"Invalid marketplace GDR {record['record_id']}: {errors}")
        records.append(record)

    records.sort(key=lambda r: -r["economics"]["primary_metric_usd"])
    return records


def classify_clinical(
    workspace: Workspace,
    profile: dict[str, Any],
    *,
    semantics_overlay: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    from analytics.clinical_runtime import capability_clinical_economics

    cr = getattr(workspace, "clinical_runs", None)
    if cr is None or cr.empty:
        return []

    vertical = profile.get("ontology_vertical", "clinical_runtime")
    semantics = load_rules_for_vertical(vertical, overlay=semantics_overlay)
    thresh = get_classification_thresholds(semantics, profile)
    priors = profile.get("priors", {})
    base = {
        "workspace_id": workspace.workspaces["workspace_id"].iloc[0]
        if len(workspace.workspaces)
        else "WS-0000"
    }
    exceptions: list[dict[str, Any]] = []

    arrival = float(priors.get("review_arrival_per_hr", 18.0))
    service = float(priors.get("review_service_per_hr", 6.0))
    servers = max(1, int(priors.get("reviewer_count", 3)))
    from analytics.queueing import erlang_c

    queue = erlang_c(arrival, service, servers)
    p_wait_min = float(thresh.get("review_sla_breach", {}).get("p_wait_min", 0.35))
    wait_min = float(thresh.get("review_sla_breach", {}).get("review_wait_hr_min", 4.0))

    for cap_id, grp in cr.groupby("capability_id"):
        cap_id = str(cap_id)
        econ = capability_clinical_economics(workspace, cap_id)
        phi_rate = float(grp["phi_in_logs"].mean())
        abstention = float(grp["abstention_rate"].mean())
        conflict_rate = float(grp["grounding_conflict"].mean())
        fhir_fail = 1.0 - float(grp["fhir_integrity_ok"].mean())
        vocab_bad = int((~grp["vocab_snapshot_ok"].astype(bool)).sum())
        injection_rate = float(grp["prompt_injection_flag"].mean())
        backlog = float(grp.loc[grp["review_required"] & ~grp["review_completed"], "review_wait_hr"].mean())
        if pd.isna(backlog):
            backlog = 0.0

        phi_min = float(thresh.get("phi_leakage", {}).get("phi_log_rate_min", 0.02))
        if phi_rate >= phi_min:
            exceptions.append({
                **base,
                "category": "phi_leakage",
                "title": f"{cap_id} — PHI in diagnostics",
                "confidence": min(0.98, 0.7 + phi_rate),
                "rank": 1,
                "impact": {"cost_usd": econ["expected_harm_usd"]},
                "capability_id": cap_id,
            })

        abst_max = float(thresh.get("abstention_collapse", {}).get("abstention_rate_max", 0.12))
        if abstention <= abst_max:
            exceptions.append({
                **base,
                "category": "abstention_collapse",
                "title": f"{cap_id} — abstention collapsed",
                "confidence": 0.82,
                "rank": 1,
                "impact": {"cost_usd": econ["review_labor_usd"] * 1.2},
                "capability_id": cap_id,
            })

        conflict_min = float(thresh.get("grounding_conflict", {}).get("conflict_rate_min", 0.08))
        if conflict_rate >= conflict_min:
            exceptions.append({
                **base,
                "category": "grounding_conflict",
                "title": f"{cap_id} — terminology conflicts",
                "confidence": 0.76,
                "rank": 2,
                "impact": {"cost_usd": econ["review_labor_usd"] * 0.5},
                "capability_id": cap_id,
            })

        fhir_min = float(thresh.get("fhir_integrity_fail", {}).get("integrity_fail_rate_min", 0.05))
        if fhir_fail >= fhir_min:
            exceptions.append({
                **base,
                "category": "fhir_integrity_fail",
                "title": f"{cap_id} — FHIR integrity failures",
                "confidence": 0.85,
                "rank": 1,
                "impact": {"cost_usd": econ["expected_harm_usd"] * 0.4},
                "capability_id": cap_id,
            })

        snap_min = int(thresh.get("vocab_snapshot_drift", {}).get("snapshot_mismatch_min", 1))
        if vocab_bad >= snap_min:
            exceptions.append({
                **base,
                "category": "vocab_snapshot_drift",
                "title": f"{cap_id} — vocabulary snapshot drift",
                "confidence": 0.7,
                "rank": 3,
                "impact": {"cost_usd": 250.0},
                "capability_id": cap_id,
            })

        inj_min = float(thresh.get("prompt_injection", {}).get("injection_rate_min", 0.03))
        if injection_rate >= inj_min:
            exceptions.append({
                **base,
                "category": "prompt_injection",
                "title": f"{cap_id} — prompt injection guard",
                "confidence": 0.9,
                "rank": 1,
                "impact": {"cost_usd": econ["expected_harm_usd"]},
                "capability_id": cap_id,
            })

        if queue.get("p_wait", 0) >= p_wait_min and backlog >= wait_min:
            exceptions.append({
                **base,
                "category": "review_sla_breach",
                "title": f"{cap_id} — review SLA breach",
                "confidence": 0.74,
                "rank": 2,
                "impact": {"cost_usd": econ["review_labor_usd"]},
                "capability_id": cap_id,
            })

        run_cost_mean = float(grp["inference_usd"].mean())
        blow_mult = float(thresh.get("run_cost_blowout", {}).get("run_cost_prior_multiplier", 1.6))
        baseline = float(priors.get("run_cost_per_success", 0.5))
        if run_cost_mean > baseline * blow_mult:
            exceptions.append({
                **base,
                "category": "run_cost_blowout",
                "title": f"{cap_id} — inference cost blowout",
                "confidence": 0.78,
                "rank": 2,
                "impact": {"cost_usd": econ["inference_usd"]},
                "capability_id": cap_id,
            })

    return exceptions


def _price_clinical_exceptions(
    exceptions: list[dict[str, Any]],
    workspace: Workspace,
    *,
    semantics: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    from analytics.clinical_runtime import capability_clinical_economics

    cap_ids = {e.get("capability_id") for e in exceptions if e.get("capability_id")}
    inference = review = harm = 0.0
    n_runs = 0
    cr = getattr(workspace, "clinical_runs", None)
    for cap_id in cap_ids:
        econ = capability_clinical_economics(workspace, str(cap_id))
        inference += econ["inference_usd"]
        review += econ["review_labor_usd"]
        harm += econ["expected_harm_usd"]
        if cr is not None and not cr.empty:
            n_runs += int((cr["capability_id"].astype(str) == str(cap_id)).sum())
    total = inference + review + harm
    if total <= 0:
        total = sum(e.get("impact", {}).get("cost_usd", 0) for e in exceptions)
    breakdown = [
        {"label": "inference", "amount_usd": round(inference, 2)},
        {"label": "review_labor", "amount_usd": round(review, 2)},
        {"label": "expected_harm", "amount_usd": round(harm, 2)},
    ]
    economics = {
        "primary_metric_usd": round(total, 2),
        "primary_metric_label": primary_metric_label(semantics, "residual_clinical_risk_usd"),
        "currency": "USD",
        "breakdown": breakdown,
    }
    cap_id = next(iter(cap_ids)) if len(cap_ids) == 1 else None
    return _finalize_economics(
        economics,
        semantics=semantics,
        profile=profile,
        workspace=workspace,
        capability_id=str(cap_id) if cap_id else None,
        production_usd=inference + review,
        risk_usd=harm,
        n_verified=n_runs or None,
    )


def emit_clinical_records(
    workspace: Workspace,
    profile: dict[str, Any],
    *,
    validate: bool = True,
    semantics_overlay: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    raw = classify_clinical(workspace, profile, semantics_overlay=semantics_overlay)
    vertical = profile.get("ontology_vertical", "clinical_runtime")
    ontology_version = profile.get("ontology_version", f"{vertical}_v1")
    semantics = load_rules_for_vertical(vertical, overlay=semantics_overlay)
    ws_id = workspace.workspaces["workspace_id"].iloc[0] if len(workspace.workspaces) else "WS-0000"

    by_cap: dict[str, list[dict]] = {}
    for e in raw:
        key = e.get("capability_id")
        if key:
            by_cap.setdefault(str(key), []).append(e)

    caps = workspace.capabilities.set_index("capability_id")
    versions = workspace.capability_versions.groupby("capability_id")["capability_version_id"].last()

    records: list[dict[str, Any]] = []
    for rec_idx, (cap_id, excs) in enumerate(by_cap.items(), start=1):
        ranked = rank_exceptions(_normalize_exceptions(excs))
        economics = _price_clinical_exceptions(
            ranked, workspace, semantics=semantics, profile=profile,
        )
        verdict = resolve_verdict(ranked, semantics)
        decision = resolve_action(verdict, semantics)
        decision["rule_trace"] = build_rule_trace(ranked, semantics, verdict, decision)
        attach_commercial(
            decision, economics, semantics=semantics, workspace=workspace, profile=profile
        )
        cap_row = caps.loc[cap_id] if cap_id in caps.index else None
        agent_id = cap_row["agent_id"] if cap_row is not None else "AGT-000"
        subject = {
            "workspace_id": ws_id,
            "entity_type": "capability",
            "capability_id": cap_id,
            "capability_version": versions.get(cap_id, f"{cap_id}-v1"),
            "agent_id": agent_id,
        }
        record = {
            "record_id": f"gdr_cln_{rec_idx:04d}",
            "vertical": vertical,
            "schema_version": "1.0.0",
            "ontology_version": ontology_version,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "evaluator_id": "churnos_emitter",
            "subject": subject,
            "exceptions": [{k: v for k, v in e.items() if k != "capability_id"} for e in ranked],
            "economics": economics,
            "decision": decision,
            "evidence": {"claim_type": "simulated"},
        }
        if validate:
            errors = validate_record(record, vertical)
            if errors:
                raise ValueError(f"Invalid clinical GDR {record['record_id']}: {errors}")
        records.append(record)

    records.sort(key=lambda r: -r["economics"]["primary_metric_usd"])
    return records


def apply_override(
    record: dict[str, Any],
    final_action: str,
    override_reason: str,
    decided_by: str = "human",
) -> dict[str, Any]:
    updated = dict(record)
    decision = dict(updated.get("decision", {}))
    decision["final_action"] = final_action
    decision["override_reason"] = override_reason
    decision["decided_by"] = decided_by
    decision["decided_at"] = datetime.now(timezone.utc).isoformat()
    updated["decision"] = decision
    return updated


def write_outcome(
    record: dict[str, Any],
    workspace: Workspace,
    horizon_days: int = 14,
) -> dict[str, Any]:
    subject = record.get("subject", {})
    entity_type = subject.get("entity_type", "capability")

    if entity_type == "account":
        acc_id = subject.get("account_id")
        seats = workspace.seats[workspace.seats["workspace_id"] == acc_id]
        seat_ids = seats["seat_id"].unique()
        subject_runs = workspace.runs[workspace.runs["seat_id"].isin(seat_ids)]
    else:
        cap_id = subject.get("capability_id")
        subject_runs = workspace.runs[workspace.runs["capability_id"] == cap_id]
        seat_ids = subject_runs["seat_id"].unique()
        seats = workspace.seats[workspace.seats["seat_id"].isin(seat_ids)]

    churn_rate = seats["is_churned"].mean() if len(seats) else 0.0
    retained = workspace.retention_marks[
        (workspace.retention_marks["seat_id"].isin(seat_ids))
        & (workspace.retention_marks["horizon_days"] == horizon_days)
    ]
    retention_delta = retained["retained"].mean() - 0.5 if len(retained) else 0.0
    if len(seats) and {"is_activated", "weekly_delegation"}.issubset(seats.columns):
        activated = seats[seats["is_activated"]]
        delegation = activated["weekly_delegation"].mean() if len(activated) else 0.0
    else:
        delegation = 0.0

    updated = dict(record)
    updated["outcome"] = {
        "retention_delta_14d": round(float(retention_delta), 4) if horizon_days == 14 else None,
        "retention_delta_28d": round(float(retention_delta), 4) if horizon_days == 28 else None,
        "churn_happened": bool(churn_rate > 0.1),
        "actual_run_cost_usd": round(float(subject_runs["run_cost_usd"].sum()), 2) if len(subject_runs) else 0.0,
        "delegation_rate": round(float(delegation), 4),
        "followed_recommendation": record.get("decision", {}).get("final_action")
        == record.get("decision", {}).get("recommended_action"),
    }
    return updated


def flywheel_evaluation(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize followed vs overridden cohorts with outcome deltas."""
    with_outcome = [r for r in records if r.get("outcome")]
    if not with_outcome:
        return {"n": 0, "followed": {}, "overridden": {}}

    followed = [r for r in with_outcome if r.get("outcome", {}).get("followed_recommendation")]
    overridden = [r for r in with_outcome if not r.get("outcome", {}).get("followed_recommendation")]

    def _avg(items: list[dict], key: str) -> float:
        vals = [r["outcome"].get(key) for r in items if r.get("outcome", {}).get(key) is not None]
        return float(sum(vals) / len(vals)) if vals else 0.0

    base = {
        "n": len(with_outcome),
        "followed": {
            "count": len(followed),
            "retention_delta_14d": _avg(followed, "retention_delta_14d"),
            "delegation_rate": _avg(followed, "delegation_rate"),
            "churn_rate": sum(1 for r in followed if r["outcome"].get("churn_happened")) / max(len(followed), 1),
        },
        "overridden": {
            "count": len(overridden),
            "retention_delta_14d": _avg(overridden, "retention_delta_14d"),
            "delegation_rate": _avg(overridden, "delegation_rate"),
            "churn_rate": sum(1 for r in overridden if r["outcome"].get("churn_happened")) / max(len(overridden), 1),
        },
    }
    causal = flywheel_causal_impact(followed, overridden)
    base["causal_impact"] = causal
    return base


def flywheel_causal_impact(
    followed: list[dict[str, Any]],
    overridden: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    CausalImpact-style teaching summary: followed vs counterfactual (overridden) cohort.
    """
    if not followed:
        return {"effect_pp": None, "ci95": None, "claim_type": "simulated"}

    f_ret = [r["outcome"].get("retention_delta_14d", 0) or 0 for r in followed]
    o_ret = [r["outcome"].get("retention_delta_14d", 0) or 0 for r in overridden] if overridden else [0.0]

    effect = float(sum(f_ret) / len(f_ret)) - float(sum(o_ret) / len(o_ret))
    se = max(0.01, abs(effect) * 0.35 + 0.01)
    ci = [round(effect - 1.96 * se, 4), round(effect + 1.96 * se, 4)]

    has_exp = any(r.get("subject", {}).get("experiment_id") for r in followed)
    return {
        "effect_pp": round(effect, 4),
        "ci95": ci,
        "claim_type": "causal" if has_exp else "simulated",
        "message": (
            f"Accounts where operators followed the recommendation retained "
            f"{effect:+.1%} vs counterfactual (95% band {ci[0]:+.1%} to {ci[1]:+.1%})."
        ),
    }


def propose_action(record: dict[str, Any], semantics: dict[str, Any]) -> tuple[str, str]:
    """Rule-based agent stub — same YAML action_map as emit_records."""
    verdict = record.get("decision", {}).get("verdict", "needs_review")
    decision = resolve_action(verdict, semantics)
    verdict_gloss = semantics.get("decision.verdict", {}).get(verdict, verdict)
    action = decision["recommended_action"]
    rationale = (
        f"Semantics-guided: {verdict} ({verdict_gloss}) → {action}. "
        f"{decision['rationale']}"
    )
    return action, rationale
