"""Headless control-plane facade used by Streamlit and the FastAPI service."""

from __future__ import annotations

from typing import Any

from analytics.decisions import (
    apply_override,
    classify,
    emit_capability_records,
    emit_records,
    propose_action,
)
from analytics.inbox import apply_triage, filter_inbox
from analytics.orchestration import emit_subgraph_records
from analytics.version_gate import evaluate_from_counts, evaluate_version_gate
from core.workspace import Workspace, build_workspace
from ontology.decision_rules import build_rule_trace
from ontology.store import append_record, log_hook, read_records, upsert_record
from ontology.validate import validate_record


def ingest_and_build(
    profile: dict[str, Any],
    *,
    seed: int = 42,
    uploaded_tables: dict[str, Any] | None = None,
    data_source: str = "synthetic",
    otel_path: str | None = None,
    n_sessions: int = 5_000,
) -> Workspace:
    return build_workspace(
        profile,
        seed=seed,
        data_source=data_source,
        otel_path=otel_path,
        uploaded_tables=uploaded_tables,
        n_sessions=n_sessions,
    )


def emit_and_store(workspace: Workspace, *, include_accounts: bool = True) -> list[dict[str, Any]]:
    records = emit_records(workspace, workspace.profile, include_accounts=include_accounts)
    for rec in records:
        _ensure_claim_type(rec, workspace)
        upsert_record(rec)
    return records


def _ensure_claim_type(record: dict[str, Any], workspace: Workspace | None = None) -> None:
    ev = dict(record.get("evidence") or {})
    if ev.get("claim_type"):
        record["evidence"] = ev
        return
    if record.get("subject", {}).get("experiment_id"):
        ev["claim_type"] = "causal"
    elif workspace is not None and (workspace.meta or {}).get("data_source") in ("synthetic", None, ""):
        ev["claim_type"] = "simulated"
    else:
        ev["claim_type"] = "associational"
    record["evidence"] = ev


__all__ = [
    "Workspace",
    "apply_override",
    "apply_triage",
    "append_record",
    "build_rule_trace",
    "classify",
    "emit_and_store",
    "emit_capability_records",
    "emit_records",
    "emit_subgraph_records",
    "evaluate_from_counts",
    "evaluate_version_gate",
    "filter_inbox",
    "ingest_and_build",
    "log_hook",
    "propose_action",
    "read_records",
    "upsert_record",
    "validate_record",
]
