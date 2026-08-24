"""Outcome Definition Kit — templates, validation, readiness gate."""

from __future__ import annotations

from typing import Any

import pandas as pd

VERIFIED_BY = ("deterministic_stage", "human_confirmation", "llm_judge", "webhook")

TEMPLATES: dict[str, dict[str, Any]] = {
    "quote_ops": {
        "label": "Quote / ops agent",
        "outcome_types": ["quote_sent", "quote_accepted", "booking_created"],
        "preferred_verified_by": "deterministic_stage",
        "notes": "Prefer deterministic pipeline stage or human confirmation.",
    },
    "support": {
        "label": "Support agent",
        "outcome_types": ["issue_resolved", "escalated", "csat_logged"],
        "preferred_verified_by": "human_confirmation",
        "notes": "Human confirmation plus survey when available.",
    },
    "analyst": {
        "label": "Analyst agent",
        "outcome_types": ["report_generated", "query_accepted", "reused"],
        "preferred_verified_by": "llm_judge",
        "notes": "Downstream reuse is stronger than LLM judge alone.",
    },
    "orchestrator": {
        "label": "Orchestrator / multi-agent",
        "outcome_types": ["task_completed", "sla_met", "no_extra_hitl"],
        "preferred_verified_by": "deterministic_stage",
        "notes": "Graph completion is the ground-truth label.",
    },
}

REQUIRED_FIELDS = (
    "outcome_id",
    "agent_run_id",
    "account_id",
    "outcome_type",
    "success",
    "verified",
    "verified_by",
)


def default_contract() -> dict[str, Any]:
    return {
        "template_id": "quote_ops",
        "outcome_types": list(TEMPLATES["quote_ops"]["outcome_types"]),
        "verified_by_policy": {t: TEMPLATES["quote_ops"]["preferred_verified_by"] for t in TEMPLATES["quote_ops"]["outcome_types"]},
        "min_verified_share": 0.40,
    }


def apply_template(template_id: str) -> dict[str, Any]:
    tpl = TEMPLATES.get(template_id) or TEMPLATES["quote_ops"]
    types = list(tpl["outcome_types"])
    return {
        "template_id": template_id,
        "outcome_types": types,
        "verified_by_policy": {t: tpl["preferred_verified_by"] for t in types},
        "min_verified_share": 0.40,
    }


def validate_outcomes(outcomes: pd.DataFrame, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = contract or default_contract()
    missing_cols = [c for c in REQUIRED_FIELDS if c not in (outcomes.columns if outcomes is not None else [])]
    n = 0 if outcomes is None or outcomes.empty else len(outcomes)
    verified_share = 0.0
    known_types_share = 0.0
    known_verified_by = 0.0
    if n:
        verified_share = float(outcomes["verified"].mean()) if "verified" in outcomes.columns else 0.0
        types = set(contract.get("outcome_types") or [])
        if types and "outcome_type" in outcomes.columns:
            known_types_share = float(outcomes["outcome_type"].isin(types).mean())
        if "verified_by" in outcomes.columns:
            known_verified_by = float(outcomes["verified_by"].isin(VERIFIED_BY).mean())
    ready = (
        n > 0
        and not missing_cols
        and verified_share >= float(contract.get("min_verified_share", 0.4))
        and bool(contract.get("outcome_types"))
    )
    blockers: list[str] = []
    if n == 0:
        blockers.append("outcomes table empty — Version Gate can still compare runs, but retention joins are blocked")
    if missing_cols:
        blockers.append(f"missing columns: {missing_cols}")
    if n and verified_share < float(contract.get("min_verified_share", 0.4)):
        blockers.append("verified share below policy floor")
    if not contract.get("outcome_types"):
        blockers.append("no outcome_types defined")
    return {
        "n": n,
        "verified_share": verified_share,
        "known_types_share": known_types_share,
        "known_verified_by_share": known_verified_by,
        "missing_columns": missing_cols,
        "ready": ready,
        "blockers": blockers,
        "claim_type": "associational" if ready else "simulated",
    }
