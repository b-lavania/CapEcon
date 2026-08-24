"""Evaluate verdicts and actions from ontology semantics (YAML-driven rules)."""

from __future__ import annotations

from typing import Any

from ontology.exception_taxonomy import ACTIONS, COMMERCIAL_ACTIONS, VERDICTS
from ontology.semantics import load_semantics


def _default_verdict_rules() -> list[dict[str, Any]]:
    return [
        {"verdict": "destructive", "when_any_category": ["capability_harm", "trust_break"]},
        {"verdict": "uneconomic", "when_any_category": ["run_cost_blowout", "cac_ltv_contradiction"]},
        {"verdict": "leaking", "when_any_category": ["activation_leak", "habit_collapse"]},
        {"verdict": "underpowered", "when_exception_count_lt": 2},
        {"verdict": "needs_review", "default": True},
    ]


def _default_action_map() -> dict[str, dict[str, Any]]:
    return {
        "healthy": {
            "recommended_action": "ship",
            "requires_review": False,
            "rationale": "No ranked exceptions above threshold.",
        },
        "leaking": {
            "recommended_action": "experiment",
            "requires_review": False,
            "rationale": "Activation or habit leak — run governed experiment before scaling.",
        },
        "destructive": {
            "recommended_action": "throttle",
            "requires_review": True,
            "rationale": "Harm or trust break — throttle until reviewed.",
        },
        "uneconomic": {
            "recommended_action": "hold",
            "requires_review": False,
            "rationale": "Economics break policy — hold rollout.",
        },
        "underpowered": {
            "recommended_action": "hold",
            "requires_review": False,
            "rationale": "Signal too thin for a confident decision.",
        },
        "needs_review": {
            "recommended_action": "hold",
            "requires_review": True,
            "rationale": "Mixed signals — human must confirm.",
        },
    }


def _default_classification_thresholds() -> dict[str, Any]:
    return {
        "capability_dead": {"max_run_count_exclusive": 5},
        "activation_leak": {"success_rate_prior_multiplier": 0.6},
        "capability_harm": {"harm_score_min": 0.08, "check_harm_correlation": True},
        "approval_fatigue": {"dismiss_rate_prior_multiplier": 1.0},
        "trust_break": {"trust_rate_prior_multiplier": 1.5},
        "run_cost_blowout": {"run_cost_prior_multiplier": 2.0},
        "loop_exhaustion": {"use_profile_max_loops": True},
        "quality_drift": {"min_slope_per_week": 0.05},
        "outcome_confirmation_gap": {"max_confirm_rate": 0.55, "min_success_rate": 0.5},
    }


def get_classification_thresholds(semantics: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Merge YAML classification thresholds with profile priors."""
    yaml_thresh = semantics.get("classification", {}).get("thresholds", {})
    merged = {**_default_classification_thresholds(), **yaml_thresh}
    priors = profile.get("priors", {})
    max_loops = float(profile.get("max_loops_threshold", 8))
    if merged.get("loop_exhaustion", {}).get("use_profile_max_loops", True):
        merged["loop_exhaustion"] = dict(merged.get("loop_exhaustion", {}))
        merged["loop_exhaustion"]["max_loops"] = max_loops
    merged["_priors"] = priors
    return merged


def resolve_verdict(exceptions: list[dict[str, Any]], semantics: dict[str, Any]) -> str:
    """First matching verdict rule wins; empty exceptions → healthy."""
    if not exceptions:
        return "healthy"

    cats = {e["category"] for e in exceptions}
    rules = semantics.get("decision", {}).get("verdict_rules", _default_verdict_rules())

    for rule in rules:
        if rule.get("when_no_exceptions"):
            continue
        when_any = rule.get("when_any_category")
        if when_any and cats.intersection(when_any):
            return rule["verdict"]
        when_all = rule.get("when_all_categories")
        if when_all and set(when_all).issubset(cats):
            return rule["verdict"]
        exc_lt = rule.get("when_exception_count_lt")
        if exc_lt is not None and len(exceptions) < exc_lt:
            return rule["verdict"]
        if rule.get("default"):
            return rule["verdict"]

    return semantics.get("decision", {}).get("verdict_default", "needs_review")


def resolve_action(verdict: str, semantics: dict[str, Any]) -> dict[str, Any]:
    """Map verdict → recommended_action, requires_review, rationale from semantics."""
    action_map = semantics.get("decision", {}).get("action_map", _default_action_map())
    spec = action_map.get(verdict, action_map.get("needs_review", _default_action_map()["needs_review"]))

    action = spec.get("recommended_action", "hold")
    if action not in ACTIONS:
        action = "hold"

    verdict_val = verdict if verdict in VERDICTS else "needs_review"

    requires_review = bool(spec.get("requires_review", verdict_val in ("needs_review", "destructive")))
    # A price or packaging change lands in someone else's system. YAML cannot waive the review.
    if action in COMMERCIAL_ACTIONS:
        requires_review = True

    return {
        "verdict": verdict_val,
        "recommended_action": action,
        "final_action": action,
        "rationale": spec.get("rationale", f"Rule-guided action for {verdict_val}."),
        "requires_review": requires_review,
    }


def load_rules_for_vertical(vertical: str, overlay: dict[str, Any] | None = None) -> dict[str, Any]:
    return load_semantics(vertical, overlay=overlay)


def find_matched_verdict_rule(
    exceptions: list[dict[str, Any]],
    semantics: dict[str, Any],
) -> dict[str, Any] | None:
    """Return the first verdict rule that would match (for provenance)."""
    if not exceptions:
        return {"verdict": "healthy", "when_no_exceptions": True}

    cats = {e["category"] for e in exceptions}
    rules = semantics.get("decision", {}).get("verdict_rules", _default_verdict_rules())
    for rule in rules:
        if rule.get("when_no_exceptions"):
            continue
        when_any = rule.get("when_any_category")
        if when_any and cats.intersection(when_any):
            return rule
        when_all = rule.get("when_all_categories")
        if when_all and set(when_all).issubset(cats):
            return rule
        exc_lt = rule.get("when_exception_count_lt")
        if exc_lt is not None and len(exceptions) < exc_lt:
            return rule
        if rule.get("default"):
            return rule
    return None


def build_rule_trace(
    exceptions: list[dict[str, Any]],
    semantics: dict[str, Any],
    verdict: str,
    decision: dict[str, Any],
) -> dict[str, Any]:
    """Human- and agent-readable provenance for a GDR decision."""
    matched = find_matched_verdict_rule(exceptions, semantics)
    action_map = semantics.get("decision", {}).get("action_map", {})
    action_spec = action_map.get(verdict, {})
    thresh = semantics.get("classification", {}).get("thresholds", {})
    return {
        "vertical": semantics.get("vertical"),
        "verdict": verdict,
        "matched_verdict_rule": matched,
        "action_map_key": verdict,
        "action_spec": {
            "recommended_action": action_spec.get("recommended_action"),
            "requires_review": action_spec.get("requires_review"),
        },
        "exception_categories": [e.get("category") for e in exceptions],
        "threshold_keys_used": list(thresh.keys())[:8],
        "rationale": decision.get("rationale", ""),
    }


def get_posterior_thresholds(semantics: dict[str, Any]) -> dict[str, float]:
    """Posterior policy thresholds from semantics overlay."""
    pt = semantics.get("classification", {}).get("posterior_thresholds", {})
    return {
        "p_churn_30d_min": float(pt.get("p_churn_30d_min", 0.5)),
        "p_uplift_churn_min": float(pt.get("p_uplift_churn_min", 0.8)),
    }


def resolve_verdict_from_posteriors(
    record: dict[str, Any],
    thresholds: dict[str, float],
) -> str | None:
    """
    Override verdict when rigorous posterior thresholds are breached.
    Returns new verdict or None to keep YAML verdict.
    """
    p_churn = record.get("p_churn_30d")
    if p_churn is not None and p_churn >= thresholds.get("p_churn_30d_min", 0.5):
        return "destructive"

    for exc in record.get("exceptions", []):
        ev = exc.get("evidence") or {}
        if ev.get("claim_type") != "causal":
            continue
        est = ev.get("estimand", "")
        if "uplift" in est:
            mean = (ev.get("posterior") or {}).get("mean", 0)
            if mean >= thresholds.get("p_uplift_churn_min", 0.8):
                return "destructive"
    return None
