"""Version Gate — pre-deploy eval, canary SPRT, post-deploy rollback GDR."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from analytics.agent_version_compare import compare_agent_versions
from analytics.commercial import attach_commercial, commercial_sentence, resolve_commercial_action
from analytics.metrics import resolve_metric
from analytics.price_block import fill_price_block, primary_metric_label
from core.workspace import Workspace
from ontology.decision_rules import build_rule_trace, load_rules_for_vertical, resolve_action
from ontology.exception_taxonomy import get_category


def _claim_type(workspace: Workspace | None, experiment_id: str | None = None) -> str:
    if experiment_id:
        return "causal"
    if workspace is None:
        return "associational"
    src = (workspace.meta or {}).get("data_source", "synthetic")
    if src in ("synthetic", None, ""):
        return "simulated"
    return "associational"


def _eval_delta(workspace: Workspace) -> dict[str, Any]:
    resolved = resolve_metric("eval_score_delta", workspace)
    return {
        "value": resolved.get("value"),
        "display": resolved.get("display"),
        "fail": (resolved.get("value") is not None and float(resolved["value"]) <= -10.0),
    }


def evaluate_from_counts(
    *,
    n_prev: int,
    s_prev: int,
    n_curr: int,
    s_curr: int,
    eval_delta: float | None = None,
    projected_cpso: float | None = None,
    policy_cpso_cap: float | None = None,
    pricing_mode: str | None = None,
    list_usd: float | None = None,
    baseline_usd: float | None = None,
) -> dict[str, Any]:
    """CI-friendly gate that does not need a Workspace."""
    from analytics.inference.sprt import sprt_two_proportion

    rate_prev = s_prev / n_prev if n_prev else 0.0
    rate_curr = s_curr / n_curr if n_curr else 0.0
    sprt = sprt_two_proportion(
        s_prev, n_prev, s_curr, n_curr,
        p0=rate_prev if rate_prev > 0 else 0.75,
        p1=max(0.01, (rate_prev if rate_prev > 0 else 0.75) - 0.08),
    )
    status = "pass"
    reasons: list[str] = []
    action = "ship"
    if eval_delta is not None and eval_delta <= -0.10:
        status = "fail"
        action = "hold"
        reasons.append(f"eval_delta {eval_delta:+.1%} beyond -10% gate")
    if projected_cpso is not None and policy_cpso_cap is not None and projected_cpso > policy_cpso_cap:
        status = "fail" if status == "fail" else "warn"
        action = "hold"
        reasons.append(f"projected CPSO ${projected_cpso:.2f} > cap ${policy_cpso_cap:.2f}")
    if sprt.get("decision") == "rollback" or (rate_curr - rate_prev) < -0.05:
        status = "fail"
        action = "rollback"
        reasons.append("canary success below control")
    elif sprt.get("decision") == "continue" or n_prev < 30 or n_curr < 30:
        if status == "pass":
            status = "warn"
            action = "hold"
        reasons.append("underpowered or SPRT continue")
    if not reasons:
        reasons.append("eval and canary within policy")

    # CI has no Workspace, so no mesh signal and no vertical YAML — defaults only.
    economics: dict[str, Any] = {
        "pricing_mode": pricing_mode or "product_sku",
        "floor_usd": projected_cpso,
        "cap_usd": policy_cpso_cap,
        "cost_basis": "estimated",
    }
    if list_usd is not None:
        economics["list_usd"] = list_usd
        economics["charged_usd"] = list_usd
    if baseline_usd is not None:
        economics["baseline_usd"] = baseline_usd
    commercial = resolve_commercial_action(economics)
    if commercial.get("commercial_action"):
        reasons.append(commercial_sentence(commercial))

    return {
        "ci_status": status,
        "recommended_action": action,
        "commercial_action": commercial.get("commercial_action"),
        "commercial_rationale": commercial.get("commercial_rationale", ""),
        "commercial_owner_role": commercial.get("commercial_owner_role"),
        "price_signal": commercial["price_signal"],
        "floor_usd": projected_cpso,
        "cap_usd": policy_cpso_cap,
        "list_usd": list_usd,
        "reasons": reasons,
        "sprt": sprt,
        "rate_prev": rate_prev,
        "rate_curr": rate_curr,
        "delta_success": rate_curr - rate_prev,
        "n_prev": n_prev,
        "n_curr": n_curr,
        "eval_delta": eval_delta,
        "claim_type": "associational",
    }


def evaluate_version_gate(workspace: Workspace, *, semantics_overlay: dict[str, Any] | None = None) -> dict[str, Any]:
    """Full gate from a Workspace: eval panel + SPRT compare + optional GDR payload."""
    cmp = compare_agent_versions(workspace)
    ev = _eval_delta(workspace)
    cpso = resolve_metric("cost_per_successful_outcome", workspace)
    trust = resolve_metric("trust_incident_rate", workspace)
    rec = cmp.get("recommendation", "hold")
    light = cmp.get("traffic_light", "yellow")
    ci_status = {"green": "pass", "yellow": "warn", "grey": "warn", "red": "fail"}.get(light, "warn")
    if ev.get("fail"):
        ci_status = "fail"
        rec = "hold"

    vertical = workspace.profile.get("ontology_vertical", "eval_governance")
    if vertical not in ("eval_governance", "agent_runtime", "capability_lifecycle"):
        vertical = "eval_governance"
    semantics = load_rules_for_vertical(vertical, overlay=semantics_overlay)
    verdict = {"ship": "healthy", "rollback": "destructive", "monitor": "needs_review", "hold": "underpowered"}.get(rec, "needs_review")
    decision = resolve_action(verdict, semantics)
    decision["recommended_action"] = rec if rec in ("ship", "hold", "rollback", "revise", "throttle") else decision["recommended_action"]
    decision["final_action"] = decision["recommended_action"]

    exceptions: list[dict[str, Any]] = []
    if rec == "rollback" or ev.get("fail"):
        cat = "eval_regression" if ev.get("fail") else "quality_drift"
        meta = get_category(cat)
        exceptions.append(
            {
                "exception_id": "exc_vg_0001",
                "category": cat,
                "title": "Version Gate failed",
                "description": meta["playbook_hint"],
                "confidence": 0.8,
                "rank": 1,
                "severity": meta["default_severity"],
                "owner": meta["owner_role"],
                "impact": {"cost_usd": float(cpso.get("value") or 0) * 1000},
            }
        )
    decision["rule_trace"] = build_rule_trace(exceptions, semantics, verdict, decision)
    experiment_id = workspace.profile.get("default_experiment_id") if rec == "ship" else None
    claim = _claim_type(workspace, experiment_id if False else None)

    capability_id = str(
        workspace.capabilities["capability_id"].iloc[0] if len(workspace.capabilities) else "CAP-000"
    )
    economics = fill_price_block(
        {
            "primary_metric_usd": float(cpso.get("value") or 0),
            "primary_metric_label": primary_metric_label(semantics, "cost_per_successful_outcome_usd"),
            "currency": "USD",
        },
        semantics=semantics,
        profile=workspace.profile,
        workspace=workspace,
        capability_id=capability_id,
    )
    commercial = resolve_commercial_action(
        economics,
        semantics=semantics,
        workspace=workspace,
        profile=workspace.profile,
    )
    attach_commercial(
        decision,
        economics,
        semantics=semantics,
        workspace=workspace,
        profile=workspace.profile,
    )

    gdr = {
        "record_id": f"gdr_version_gate_{cmp.get('current_version', 'curr')}",
        "vertical": vertical,
        "schema_version": "1.0.0",
        "ontology_version": workspace.profile.get("ontology_version", f"{vertical}_v1"),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "evaluator_id": "version_gate",
        "subject": {
            "entity_type": "capability",
            "capability_id": capability_id,
            "capability_version": str(cmp.get("current_version", "")),
            "account_id": str(workspace.accounts["account_id"].iloc[0]) if len(getattr(workspace, "accounts", [])) else "ACC-000",
        },
        "exceptions": exceptions,
        "economics": economics,
        "decision": decision,
        "evidence": {
            "claim_type": claim,
            "caption": cmp.get("reason", ""),
            "n": int(cmp.get("n_prev", 0) or 0) + int(cmp.get("n_curr", 0) or 0),
        },
    }

    return {
        "ci_status": ci_status,
        "recommended_action": rec,
        "compare": cmp,
        "eval_delta": ev,
        "cpso": cpso,
        "trust_incident_rate": trust,
        "gdr": gdr,
        "claim_type": claim,
        "economics": economics,
        "commercial": commercial,
        "reasons": [cmp.get("reason", "")] + (["eval regression"] if ev.get("fail") else []),
    }
