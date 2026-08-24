"""Decision Inbox — triage state over GrowthDecisionRecords."""

from __future__ import annotations

from typing import Any

from ontology.exception_taxonomy import CATEGORIES, get_category
from ontology.store import get_triage, list_triage, set_triage, upsert_record

TRIAGE_STATES = ("pending", "in_review", "resolved", "overridden", "deferred")

# Design-partner identity: role → display name. No login.
ROLE_OWNERS: dict[str, str] = {
    "growth_lead": "Alex (growth)",
    "product": "Sam (product)",
    "data_science": "Riley (DS)",
    "engineering": "Jordan (eng)",
    "founder": "Pat (ops lead)",
    "finance": "Morgan (finance)",
    "customer_success": "Casey (CS)",
    "packaging": "Devi (packaging)",
    "deal_desk": "Noor (deal desk)",
    "platform": "Kai (platform)",
}


def owner_for_record(record: dict[str, Any]) -> str:
    excs = record.get("exceptions") or []
    if not excs:
        return record.get("decision", {}).get("owner") or "product"
    return excs[0].get("owner") or get_category(excs[0].get("category", "instrumentation_debt")).get("owner_role", "product")


def commercial_owner_for_record(record: dict[str, Any]) -> str | None:
    """Second owner. The ops owner throttles; this one changes the price book."""
    decision = record.get("decision") or {}
    if not decision.get("commercial_action"):
        return None
    return decision.get("commercial_owner_role") or "packaging"


def enrich_inbox(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    triage_map = list_triage()
    out: list[dict[str, Any]] = []
    for rec in records:
        item = dict(rec)
        rid = rec.get("record_id")
        tri = triage_map.get(rid) or get_triage(rid) or {}
        role = owner_for_record(rec)
        item["inbox"] = {
            "status": tri.get("status") or "pending",
            "assignee": tri.get("assignee") or ROLE_OWNERS.get(role, role),
            "owner_role": tri.get("owner_role") or role,
            "notes": tri.get("notes") or "",
        }
        out.append(item)
    return out


def filter_inbox(
    records: list[dict[str, Any]],
    *,
    owner_role: str | None = None,
    status: str | None = None,
    requires_review: bool | None = None,
    verdict: str | None = None,
) -> list[dict[str, Any]]:
    items = enrich_inbox(records)
    if owner_role and owner_role != "all":
        items = [r for r in items if r.get("inbox", {}).get("owner_role") == owner_role]
    if status and status != "all":
        items = [r for r in items if r.get("inbox", {}).get("status") == status]
    if requires_review is True:
        items = [r for r in items if r.get("decision", {}).get("requires_review")]
    if verdict and verdict != "all":
        items = [r for r in items if r.get("decision", {}).get("verdict") == verdict]
    items.sort(key=lambda r: -float((r.get("economics") or {}).get("primary_metric_usd") or 0))
    return items


def apply_triage(record: dict[str, Any], status: str, *, notes: str | None = None, assignee: str | None = None) -> dict[str, Any]:
    if status not in TRIAGE_STATES:
        raise ValueError(f"unknown triage status {status}")
    rid = record["record_id"]
    set_triage(
        rid,
        status=status,
        notes=notes,
        assignee=assignee,
        owner_role=owner_for_record(record),
    )
    upsert_record(record)
    return enrich_inbox([record])[0]


def owner_roles() -> list[str]:
    return sorted({v["owner_role"] for v in CATEGORIES.values()})
