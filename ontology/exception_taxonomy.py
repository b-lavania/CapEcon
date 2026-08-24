"""Ontology exception taxonomy for agentic growth decisions."""

from __future__ import annotations

from typing import Any

CATEGORIES: dict[str, dict[str, Any]] = {
    "activation_leak": {
        "owner_role": "growth_lead",
        "default_severity": "high",
        "playbook_hint": "Diagnose first trusted successful run; fix onboarding connectors.",
    },
    "habit_collapse": {
        "owner_role": "product",
        "default_severity": "high",
        "playbook_hint": "Compare week-1 vs week-4 delegation; inspect dismiss rates.",
    },
    "capability_harm": {
        "owner_role": "data_science",
        "default_severity": "high",
        "playbook_hint": "Associational only unless experiment_id present; throttle or shadow.",
    },
    "capability_dead": {
        "owner_role": "engineering",
        "default_severity": "medium",
        "playbook_hint": "Low adoption after ship; kill or merge capability.",
    },
    "approval_fatigue": {
        "owner_role": "product",
        "default_severity": "medium",
        "playbook_hint": "Reduce review queue; raise autonomy thresholds carefully.",
    },
    "trust_break": {
        "owner_role": "founder",
        "default_severity": "high",
        "playbook_hint": "Trust incidents correlate with churn; rollback immediately.",
    },
    "connector_fragility": {
        "owner_role": "engineering",
        "default_severity": "medium",
        "playbook_hint": "Map blast radius across dependent capabilities.",
    },
    "run_cost_blowout": {
        "owner_role": "finance",
        "default_severity": "medium",
        "playbook_hint": "Compare $/successful run vs seat ARPU and credit burn.",
    },
    "loop_exhaustion": {
        "owner_role": "engineering",
        "default_severity": "high",
        "playbook_hint": "Agent exceeded loop budget; inspect planning step for goal drift or tool-call hallucination.",
    },
    "quality_drift": {
        "owner_role": "data_science",
        "default_severity": "high",
        "playbook_hint": "Steps-to-completion trending up; output quality degrading before users notice.",
    },
    "eval_regression": {
        "owner_role": "data_science",
        "default_severity": "high",
        "playbook_hint": "Offline eval score dropped >10% from prior version; do not ship until re-evaluated.",
    },
    "outcome_confirmation_gap": {
        "owner_role": "product",
        "default_severity": "medium",
        "playbook_hint": "Run succeeds but downstream write events not observed; agent may be producing orphaned artifacts.",
    },
    "eval_drift": {
        "owner_role": "data_science",
        "default_severity": "medium",
        "playbook_hint": "Offline eval no longer predicts online outcomes.",
    },
    "cac_ltv_contradiction": {
        "owner_role": "growth_lead",
        "default_severity": "high",
        "playbook_hint": "Growth lever violates payback policy.",
    },
    "instrumentation_debt": {
        "owner_role": "engineering",
        "default_severity": "low",
        "playbook_hint": "Cannot decide; events lack typed contract.",
    },
    # Account churn reason codes (methodology §4.3)
    "tourist": {
        "owner_role": "growth_lead",
        "default_severity": "high",
        "playbook_hint": "No verified outcome within 14d — onboarding or ICP mismatch.",
    },
    "value_failure": {
        "owner_role": "product",
        "default_severity": "high",
        "playbook_hint": "Outcome drift down + delegation declining — perceived value gap.",
    },
    "efficiency": {
        "owner_role": "product",
        "default_severity": "medium",
        "playbook_hint": "Delegation down while success stable — workflow friction or fatigue.",
    },
    "displacement": {
        "owner_role": "growth_lead",
        "default_severity": "medium",
        "playbook_hint": "Competitive displacement signal — usage cliff without trust break.",
    },
    "price": {
        "owner_role": "finance",
        "default_severity": "medium",
        "playbook_hint": "$/outcome above plan threshold — price sensitivity.",
    },
    "champion_departure": {
        "owner_role": "customer_success",
        "default_severity": "high",
        "playbook_hint": "Primary seat churned while account still active — champion risk.",
    },
    "product_gap": {
        "owner_role": "product",
        "default_severity": "medium",
        "playbook_hint": "Activation without habit — missing capability or connector.",
    },
    "activation_failure": {
        "owner_role": "growth_lead",
        "default_severity": "high",
        "playbook_hint": "High % of paid accounts with zero verified outcome in 14d — force guided first-win.",
    },
    "margin_leakage": {
        "owner_role": "finance",
        "default_severity": "high",
        "playbook_hint": "Top power users show negative contribution margin under flat pricing.",
    },
    "catastrophic_failure": {
        "owner_role": "engineering",
        "default_severity": "critical",
        "playbook_hint": "Irreversible negative agent action — immediate rollback and trust intervention.",
    },
    "platform_margin_erosion": {
        "owner_role": "finance",
        "default_severity": "high",
        "playbook_hint": "Agent-assisted margin below manual baseline — throttle or revisit take rate.",
    },
    "agent_gmv_concentration": {
        "owner_role": "product",
        "default_severity": "medium",
        "playbook_hint": "Too much GMV through one workflow — diversify agent assists.",
    },
    "transaction_verification_gap": {
        "owner_role": "engineering",
        "default_severity": "high",
        "playbook_hint": "Agent claims success without webhook/deterministic confirmation.",
    },
    "inference_cost_blowout": {
        "owner_role": "finance",
        "default_severity": "high",
        "playbook_hint": "Per-transaction inference exceeds platform take revenue.",
    },
    "outcome_mix_drift": {
        "owner_role": "data_science",
        "default_severity": "medium",
        "playbook_hint": "Outcome mix shifted — investigate version or policy change.",
    },
    "handoff_failure": {
        "owner_role": "engineering",
        "default_severity": "high",
        "playbook_hint": "A→B agent handoff fails or retries — inspect routing policy and subgraph ownership.",
    },
    "trust_boundary": {
        "owner_role": "founder",
        "default_severity": "high",
        "playbook_hint": "Agent called a connector/capability outside its declared trust boundary.",
    },
    "orphaned_subtask": {
        "owner_role": "engineering",
        "default_severity": "high",
        "playbook_hint": "Subagent started and never completed — kill subgraph or add a timeout gate.",
    },
    "coordination_cost": {
        "owner_role": "finance",
        "default_severity": "medium",
        "playbook_hint": "Multi-agent coordination cost exceeds outcome value — simplify the graph.",
    },
    "phi_leakage": {
        "owner_role": "engineering",
        "default_severity": "critical",
        "playbook_hint": "Raw PHI in logs, diagnostics, or GDR — rollback and scrub before any egress.",
    },
    "abstention_collapse": {
        "owner_role": "data_science",
        "default_severity": "high",
        "playbook_hint": "Calibrated abstention rate crashed — false-present findings flood review.",
    },
    "grounding_conflict": {
        "owner_role": "data_science",
        "default_severity": "high",
        "playbook_hint": "Terminology conflict without explicit resolution — shadow until reconciled.",
    },
    "fhir_integrity_fail": {
        "owner_role": "engineering",
        "default_severity": "high",
        "playbook_hint": "Bundle reference integrity or assertion-context loss — do not ship export.",
    },
    "vocab_snapshot_drift": {
        "owner_role": "engineering",
        "default_severity": "medium",
        "playbook_hint": "Checksum-pinned vocabulary snapshot mismatch — hold until snapshots align.",
    },
    "prompt_injection": {
        "owner_role": "engineering",
        "default_severity": "critical",
        "playbook_hint": "MCP or prompt-injection guard tripped — rollback tool surface.",
    },
    "review_sla_breach": {
        "owner_role": "product",
        "default_severity": "high",
        "playbook_hint": "HITL review queue exceeds SLA — throttle intake or add reviewer capacity.",
    },
}

CHURN_REASON_CODES = [
    "tourist",
    "value_failure",
    "efficiency",
    "displacement",
    "price",
    "champion_departure",
    "product_gap",
]

VERDICTS = ["healthy", "leaking", "destructive", "uneconomic", "underpowered", "needs_review"]

OPS_ACTIONS = ["ship", "hold", "throttle", "shadow", "rollback", "kill", "experiment", "revise"]

# Commercial actions change the price or the packaging, never the runtime.
# Every one of these is a request into someone else's system and always requires review.
COMMERCIAL_ACTIONS = [
    "hold_sku",
    "raise_list",
    "split_tier",
    "cut_credits",
    "kill_all_inclusive",
    "reallocate",
]

ACTIONS = OPS_ACTIONS + COMMERCIAL_ACTIONS

COMMERCIAL_OWNER_ROLES = ["packaging", "finance", "deal_desk"]


def get_category(key: str) -> dict[str, Any]:
    return CATEGORIES[key]


def all_categories() -> list[str]:
    return list(CATEGORIES.keys())
