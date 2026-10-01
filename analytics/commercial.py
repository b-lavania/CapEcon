"""Commercial actions — what the price block says to do about price or packaging.

Two axes, one decision. The ops action changes the runtime (`ship`, `hold`,
`rollback`). The commercial action changes the price book (`raise_list`,
`split_tier`) or the routing that feeds it (`reallocate`). They are separate
because "the model is fine but we are selling it below cost" is a real state.

Python computes the signal, YAML picks the verb. Same split as verdict rules:
`resolve_price_signal` reads numbers, `decision.commercial_action_map` in
semantics decides what the number means for this vertical.
"""

from __future__ import annotations

from typing import Any

from core.workspace import Workspace
from ontology.exception_taxonomy import COMMERCIAL_ACTIONS

PRICE_SIGNALS = (
    "unpriceable",
    "within_policy",
    "mesh_leak",
    "below_tier_list",
    "list_below_demand_opt",
    "below_floor",
    "over_baseline",
    "flat_bucket_over_cap",
    "severely_over_cap",
    "over_cap",
    "token_bloat",
    "agency_deficit",
)

COMMERCIAL_OWNERS = {
    "hold_sku": "packaging",
    "raise_list": "finance",
    "split_tier": "packaging",
    "cut_credits": "packaging",
    "kill_all_inclusive": "packaging",
    "reallocate": "platform",
    "dynamic_cascade": "platform",
    "spot_audit_hitl": "operations",
}

_FLAT_BILLING = frozenset({"b2b_subscription", "seat_based", "flat"})


def _default_commercial_thresholds() -> dict[str, float]:
    return {
        "retry_amplification_max": 3.0,
        "coordination_cost_ratio_max": 35.0,
        "severe_overage_multiple": 2.0,
        "demand_opt_gap": 0.85,
    }


def get_commercial_thresholds(semantics: dict[str, Any] | None) -> dict[str, float]:
    yaml_thresh = (semantics or {}).get("decision", {}).get("commercial_thresholds", {})
    merged = {**_default_commercial_thresholds()}
    for key, val in (yaml_thresh or {}).items():
        try:
            merged[key] = float(val)
        except (TypeError, ValueError):
            continue
    return merged


def _default_commercial_action_map() -> dict[str, dict[str, Any]]:
    return {
        "unpriceable": {
            "commercial_action": None,
            "rationale": "No floor or no reference price — CapEcon will not make a commercial call.",
        },
        "within_policy": {
            "commercial_action": None,
            "rationale": "Floor sits inside the cap. Nothing to ask packaging for.",
        },
        "mesh_leak": {
            "commercial_action": "reallocate",
            "rationale": "Retry or coordination tax is inflating the floor. Change routing before you touch price.",
        },
        "below_tier_list": {
            "commercial_action": "raise_list",
            "rationale": "Floor exceeds the S/M/L list price for this scoped task.",
        },
        "list_below_demand_opt": {
            "commercial_action": "raise_list",
            "rationale": "Current list sits below the surplus-optimal price from fitted demand.",
        },
        "below_floor": {
            "commercial_action": "raise_list",
            "rationale": "Every verified outcome is sold under what it costs to produce.",
        },
        "over_baseline": {
            "commercial_action": "hold_sku",
            "rationale": "The agent costs more per outcome than the human baseline it replaced.",
        },
        "flat_bucket_over_cap": {
            "commercial_action": "kill_all_inclusive",
            "rationale": "A flat bucket cannot absorb this floor — the heavy cohort is subsidised.",
        },
        "severely_over_cap": {
            "commercial_action": "hold_sku",
            "rationale": "Floor is a multiple of the cap. Stop selling more of this before repricing.",
        },
        "over_cap": {
            "commercial_action": "split_tier",
            "rationale": "Floor breaches the cap — fence the expensive cohort.",
        },
        "token_bloat": {
            "commercial_action": "dynamic_cascade",
            "rationale": "Token spend saturated with negligible lift — down-route to cheaper tier.",
        },
        "agency_deficit": {
            "commercial_action": "spot_audit_hitl",
            "rationale": "Review labor exceeds savings vs human baseline — spot-check to reduce verification tax.",
        },
    }


def get_commercial_action_map(semantics: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    yaml_map = (semantics or {}).get("decision", {}).get("commercial_action_map")
    if not yaml_map:
        return _default_commercial_action_map()
    return {**_default_commercial_action_map(), **yaml_map}


def _mesh_leak(workspace: Workspace | None, thresholds: dict[str, float]) -> tuple[bool, str]:
    """True when the floor is inflated by retries or handoffs rather than by unit price."""
    if workspace is None:
        return False, ""
    from analytics.challenge_metrics import retry_amplification_factor
    from analytics.orchestration import coordination_cost_ratio

    try:
        retries = float(retry_amplification_factor(workspace))
    except Exception:
        retries = 0.0
    try:
        coord = float(coordination_cost_ratio(workspace))
    except Exception:
        coord = 0.0

    if retries >= thresholds["retry_amplification_max"]:
        return True, f"retry amplification {retries:.1f}x"
    if coord >= thresholds["coordination_cost_ratio_max"]:
        return True, f"coordination cost {coord:.0f}% of spend"
    return False, ""


def resolve_price_signal(
    economics: dict[str, Any],
    *,
    workspace: Workspace | None = None,
    semantics: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """First matching signal wins. Returns the signal plus the numbers behind it."""
    thresholds = get_commercial_thresholds(semantics)
    floor = economics.get("floor_usd")
    cap = economics.get("cap_usd")
    charged = economics.get("charged_usd")
    if charged is None:
        charged = economics.get("list_usd")
    baseline = economics.get("baseline_usd")
    mode = economics.get("pricing_mode") or "internal_budget"
    billing = (profile or {}).get("billing_model")

    if floor is None:
        return {"price_signal": "unpriceable", "detail": "no floor — no verified outcomes to divide by"}
    floor = float(floor)

    references = [r for r in (cap, charged, baseline) if r is not None]
    if not references:
        return {"price_signal": "unpriceable", "detail": "floor exists but no cap, list, or baseline to compare it against"}

    if economics.get("price_signal") in ("token_bloat", "agency_deficit"):
        sig = economics["price_signal"]
        return {"price_signal": sig, "detail": economics.get("detail", f"{sig} detected")}
    if economics.get("token_bloat"):
        return {"price_signal": "token_bloat", "detail": "saturated MOPT with elevated token cost"}
    if economics.get("agency_deficit"):
        return {"price_signal": "agency_deficit", "detail": "verification and inference exceed human baseline"}

    over_cap = cap is not None and floor > float(cap)

    if over_cap:
        leaking, why = _mesh_leak(workspace, thresholds)
        if leaking:
            return {"price_signal": "mesh_leak", "detail": why}

    tier_list = economics.get("tier_list_usd")
    if tier_list is not None and floor > float(tier_list):
        gap = floor - float(tier_list)
        return {
            "price_signal": "below_tier_list",
            "detail": f"floor ${floor:.2f} vs tier list ${float(tier_list):.2f} (${gap:.2f} gap)",
        }

    surplus_opt = economics.get("surplus_opt_usd")
    list_ref = charged
    gap_thresh = thresholds.get("demand_opt_gap", 0.85)
    if (
        surplus_opt is not None
        and list_ref is not None
        and float(surplus_opt) > floor
        and float(list_ref) < gap_thresh * float(surplus_opt)
    ):
        return {
            "price_signal": "list_below_demand_opt",
            "detail": f"list ${float(list_ref):.2f} vs surplus-opt ${float(surplus_opt):.2f}",
        }

    if charged is not None and floor > float(charged):
        gap = floor - float(charged)
        return {"price_signal": "below_floor", "detail": f"${gap:.2f} lost per verified outcome"}

    if mode == "internal_budget" and baseline is not None and floor > float(baseline):
        return {
            "price_signal": "over_baseline",
            "detail": f"floor ${floor:.2f} vs human baseline ${float(baseline):.2f}",
        }

    if over_cap:
        multiple = floor / float(cap) if float(cap) > 0 else float("inf")
        if multiple >= thresholds["severe_overage_multiple"]:
            return {"price_signal": "severely_over_cap", "detail": f"{multiple:.1f}x the cap"}
        if mode == "product_sku" and billing in _FLAT_BILLING:
            return {"price_signal": "flat_bucket_over_cap", "detail": f"flat {billing} at {multiple:.1f}x cap"}
        return {"price_signal": "over_cap", "detail": f"{multiple:.1f}x the cap"}

    return {"price_signal": "within_policy", "detail": ""}


def resolve_commercial_action(
    economics: dict[str, Any],
    *,
    semantics: dict[str, Any] | None = None,
    workspace: Workspace | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Signal → verb via YAML. Unknown verbs are dropped, never silently downgraded."""
    signal = resolve_price_signal(
        economics, workspace=workspace, semantics=semantics, profile=profile
    )
    key = signal["price_signal"]
    spec = get_commercial_action_map(semantics).get(key, {})
    action = spec.get("commercial_action")

    if action is not None and action not in COMMERCIAL_ACTIONS:
        return {
            "price_signal": key,
            "commercial_action": None,
            "commercial_rationale": (
                f"semantics mapped `{key}` to unknown commercial action `{action}` — dropped"
            ),
            "price_signal_detail": signal.get("detail", ""),
        }

    rationale = spec.get("rationale", "")
    detail = signal.get("detail", "")
    if detail and rationale:
        rationale = f"{rationale} ({detail})"

    out = {
        "price_signal": key,
        "commercial_action": action,
        "commercial_rationale": rationale,
        "price_signal_detail": detail,
    }
    if action:
        out["commercial_owner_role"] = COMMERCIAL_OWNERS.get(action, "packaging")
        out["requires_review"] = True
    return out


def attach_commercial(
    decision: dict[str, Any],
    economics: dict[str, Any],
    *,
    semantics: dict[str, Any] | None = None,
    workspace: Workspace | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add the commercial axis to a decision in place. Every emit site calls this."""
    commercial = resolve_commercial_action(
        economics, semantics=semantics, workspace=workspace, profile=profile
    )
    decision["price_signal"] = commercial["price_signal"]
    decision["commercial_action"] = commercial.get("commercial_action")
    decision["commercial_rationale"] = commercial.get("commercial_rationale", "")
    if commercial.get("commercial_owner_role"):
        decision["commercial_owner_role"] = commercial["commercial_owner_role"]
    if commercial.get("requires_review"):
        decision["requires_review"] = True
    return decision


def commercial_sentence(commercial: dict[str, Any]) -> str:
    """One line for the card and the CI comment."""
    action = commercial.get("commercial_action")
    if not action:
        signal = commercial.get("price_signal", "unpriceable")
        if signal == "within_policy":
            return "No commercial action — floor is inside the cap."
        return f"No commercial action — {commercial.get('commercial_rationale') or signal}."
    owner = commercial.get("commercial_owner_role", "packaging")
    return f"{action} → {owner}: {commercial.get('commercial_rationale', '')}"
