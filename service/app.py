"""Thin FastAPI control plane — CI and hooks call this, Streamlit uses the same library."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from analytics.inbox import apply_triage, filter_inbox
from analytics.version_gate import evaluate_from_counts
from ontology.store import list_hooks, log_hook, read_records, upsert_record

app = FastAPI(
    title="churnOS control plane",
    description="Decision layer for enterprise agent operations. Metadata only — no prompt bodies.",
    version="0.1.0",
)


class CountsGateRequest(BaseModel):
    n_prev: int
    s_prev: int
    n_curr: int
    s_curr: int
    eval_delta: float | None = None
    projected_cpso: float | None = None
    policy_cpso_cap: float | None = None
    pricing_mode: str | None = None
    list_usd: float | None = None
    baseline_usd: float | None = None


class IngestAck(BaseModel):
    status: str
    tables: list[str] = Field(default_factory=list)
    n_spans: int = 0
    n_runs: int = 0
    note: str = "Use Streamlit Data Connect or pass tables into core.control_plane.ingest_and_build"


class OverrideBody(BaseModel):
    final_action: str
    reason: str = ""
    decided_by: str = "api"


class TriageBody(BaseModel):
    status: str
    notes: str | None = None
    assignee: str | None = None


class HookBody(BaseModel):
    hook: str
    record_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest")
def ingest() -> IngestAck:
    """Placeholder ack — file ingest is local (VPC). CI should post counts to /version-gate."""
    return IngestAck(status="accepted", note="POST traces via Data Connect or ingest_and_build(); this endpoint is the contract stub.")


@app.post("/version-gate")
def version_gate(body: CountsGateRequest) -> dict[str, Any]:
    result = evaluate_from_counts(
        n_prev=body.n_prev,
        s_prev=body.s_prev,
        n_curr=body.n_curr,
        s_curr=body.s_curr,
        eval_delta=body.eval_delta,
        projected_cpso=body.projected_cpso,
        policy_cpso_cap=body.policy_cpso_cap,
        pricing_mode=body.pricing_mode,
        list_usd=body.list_usd,
        baseline_usd=body.baseline_usd,
    )
    log_hook(
        "version-gate",
        detail={
            "ci_status": result.get("ci_status"),
            "action": result.get("recommended_action"),
            "commercial_action": result.get("commercial_action"),
            "price_signal": result.get("price_signal"),
        },
    )
    return result


@app.get("/decisions")
def decisions(
    owner_role: str | None = None,
    status: str | None = None,
    verdict: str | None = None,
) -> dict[str, Any]:
    records = read_records()
    items = filter_inbox(records, owner_role=owner_role, status=status, verdict=verdict)
    return {"n": len(items), "records": items}


@app.post("/decisions/{record_id}/override")
def override_decision(record_id: str, body: OverrideBody) -> dict[str, Any]:
    from analytics.decisions import apply_override

    records = read_records()
    rec = next((r for r in records if r.get("record_id") == record_id), None)
    if rec is None:
        raise HTTPException(status_code=404, detail="record not found")
    updated = apply_override(rec, body.final_action, body.reason, decided_by=body.decided_by)
    upsert_record(updated)
    apply_triage(updated, "overridden" if body.final_action != rec.get("decision", {}).get("recommended_action") else "resolved")
    log_hook("override", record_id=record_id, detail={"action": body.final_action})
    return updated


@app.post("/decisions/{record_id}/triage")
def triage_decision(record_id: str, body: TriageBody) -> dict[str, Any]:
    records = read_records()
    rec = next((r for r in records if r.get("record_id") == record_id), None)
    if rec is None:
        raise HTTPException(status_code=404, detail="record not found")
    updated = apply_triage(rec, body.status, notes=body.notes, assignee=body.assignee)
    return updated


@app.post("/hooks/invoke")
def invoke_hook(body: HookBody) -> dict[str, str]:
    log_hook(body.hook, record_id=body.record_id, detail=body.detail)
    return {"status": "logged", "hook": body.hook}


@app.get("/hooks/audit")
def hook_audit(limit: int = 50) -> dict[str, Any]:
    return {"events": list_hooks(limit=limit)}


def create_app() -> FastAPI:
    return app
