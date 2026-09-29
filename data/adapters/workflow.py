"""Workflow adapter: OTel / Langfuse / LangGraph node dumps → Workspace runs and spans."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from data.adapters.base import (
    RUNS_COLUMNS,
    SPANS_COLUMNS,
    align_frame,
    as_bool,
    as_float,
    load_json_or_jsonl,
    stamp_provenance,
)

APPROVALS_COLUMNS = ["approval_id", "run_id", "seat_id", "decision", "decided_at"]


def ingest_workflow_export(path: str | Path, *, kind: str | None = None) -> dict[str, Any]:
    """
    Ingest a workflow export.

    kind: "otel" | "langfuse" | "langgraph" | None (auto-detect from content).
    """
    p = Path(path)
    if kind == "otel":
        from data.adapters.otel import ingest_otel_export

        tables = ingest_otel_export(p)
        return {
            "tables": tables,
            "meta": stamp_provenance("workflow", claim_type="associational", extra={"format": "otel"}),
        }

    if kind == "langfuse":
        from data.adapters.langfuse import ingest_langfuse_export

        tables = ingest_langfuse_export(p)
        return {
            "tables": tables,
            "meta": stamp_provenance("workflow", claim_type="associational", extra={"format": "langfuse"}),
        }

    records = load_json_or_jsonl(p)
    if not records:
        empty = {
            "runs": pd.DataFrame(columns=RUNS_COLUMNS),
            "spans": pd.DataFrame(columns=SPANS_COLUMNS),
        }
        return {"tables": empty, "meta": stamp_provenance("workflow")}

    first = records[0]
    if "node_executions" in first or kind == "langgraph":
        if "node_executions" in first:
            return ingest_langgraph_records(records)
        return ingest_langgraph_records([{"node_executions": records}])

    if "node_id" in first or "node_name" in first:
        return ingest_langgraph_records([{"node_executions": records, "workspace_id": "wf"}])

    from data.adapters.otel import ingest_otel_records

    tables = ingest_otel_records(records)
    return {
        "tables": tables,
        "meta": stamp_provenance("workflow", claim_type="associational", extra={"format": "otel"}),
    }


def ingest_langgraph_records(wrappers: list[dict[str, Any]]) -> dict[str, Any]:
    run_rows: list[dict[str, Any]] = []
    span_rows: list[dict[str, Any]] = []
    approval_rows: list[dict[str, Any]] = []

    for wi, wrap in enumerate(wrappers):
        nodes = wrap.get("node_executions") or []
        workspace = str(wrap.get("workspace_id") or f"ws-{wi}")
        for i, node in enumerate(nodes):
            if not isinstance(node, dict):
                continue
            run_id = str(node.get("node_id") or node.get("run_id") or f"LG-{wi}-{i:04d}")
            cost = as_float(node.get("cost_usd") or node.get("run_cost_usd"), 0.0)
            success = node.get("error") in (None, "", False) and as_bool(node.get("success"), True)
            retries = int(node.get("retry_count") or 0)
            seat = str(node.get("seat_id") or workspace)
            cap = str(node.get("node_name") or node.get("capability_id") or "langgraph_node")
            started = node.get("started_at") or "2026-01-01T00:00:00Z"

            run_rows.append(
                {
                    "run_id": run_id,
                    "seat_id": seat,
                    "capability_id": cap,
                    "capability_version_id": str(node.get("capability_version_id") or f"{cap}:v1"),
                    "started_at": started,
                    "success": success,
                    "run_cost_usd": cost,
                    "trust_incident": as_bool(node.get("trust_incident"), False),
                    "loop_count": retries + 1,
                }
            )
            for r in range(retries + 1):
                span_rows.append(
                    {
                        "span_id": f"{run_id}-span-{r}",
                        "agent_run_id": run_id,
                        "session_id": workspace,
                        "loop_iteration": r,
                        "tokens_in": int(node.get("tokens_in") or 0),
                        "tokens_out": int(node.get("tokens_out") or 0),
                        "success": success if r == retries else False,
                    }
                )
            if node.get("human_intervened") or node.get("approval_decision"):
                approval_rows.append(
                    {
                        "approval_id": f"APR-{run_id}",
                        "run_id": run_id,
                        "seat_id": seat,
                        "decision": str(node.get("approval_decision") or "confirmed"),
                        "decided_at": started,
                    }
                )

    tables: dict[str, pd.DataFrame] = {
        "runs": align_frame(run_rows, RUNS_COLUMNS),
        "spans": align_frame(span_rows, SPANS_COLUMNS),
    }
    if approval_rows:
        tables["approvals"] = align_frame(approval_rows, APPROVALS_COLUMNS)
    return {
        "tables": tables,
        "meta": stamp_provenance("workflow", claim_type="simulated", extra={"format": "langgraph"}),
    }
