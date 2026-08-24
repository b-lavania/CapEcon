"""OTel JSONL adapter — metadata-only runs/spans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from data.adapters.scrub import scrub_payload, span_has_content
from data.otel_mock_generator import load_otel_traces

SPANS_COLUMNS = [
    "span_id",
    "agent_run_id",
    "session_id",
    "parent_span_id",
    "loop_iteration",
    "tokens_in",
    "tokens_out",
    "success",
    "trace_id",
    "data_source",
    "capability_id",
    "model_id",
    "scrubbed",
]

RUNS_COLUMNS = [
    "run_id",
    "capability_id",
    "success",
    "tokens_in",
    "tokens_out",
    "loop_count",
    "trace_id",
    "data_source",
]


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def ingest_otel_export(path: str | Path) -> dict[str, pd.DataFrame]:
    """
    Parse OTel-style JSONL (one span or one trace wrapper per line).

    Accepts the repo mock format and a subset of GenAI semantic conventions
    (`gen_ai.*` token attributes). Always scrubs prompt bodies.
    """
    raw = load_otel_traces(path)
    if not raw:
        # allow a JSON array file
        p = Path(path)
        if p.exists():
            text = p.read_text(encoding="utf-8").strip()
            if text.startswith("["):
                raw = json.loads(text)
    return ingest_otel_records(raw)


def ingest_otel_records(records: list[dict[str, Any]]) -> dict[str, pd.DataFrame]:
    span_rows: list[dict[str, Any]] = []
    run_acc: dict[str, dict[str, Any]] = {}

    for rec in records:
        rec = scrub_payload(dict(rec))
        if span_has_content(rec):
            rec = scrub_payload(rec)

        # Unwrap resourceSpans-style payloads if present
        if "resourceSpans" in rec:
            continue  # nested OTLP protobuf JSON is out of scope; use flat JSONL

        trace_id = str(rec.get("trace_id") or rec.get("traceId") or rec.get("span_id") or "")
        span_id = str(rec.get("span_id") or rec.get("spanId") or f"SPN-{trace_id[:8]}")
        parent = rec.get("parent_span_id") or rec.get("parentSpanId")
        cap_id = str(rec.get("capability_id") or rec.get("gen_ai.agent.id") or "CAP-000")
        tokens = rec.get("tokens_used")
        if tokens is None:
            tokens = rec.get("gen_ai.usage.input_tokens") or rec.get("tokens_in") or 0
        tokens_in = _as_int(tokens)
        tokens_out = _as_int(rec.get("tokens_out") or rec.get("gen_ai.usage.output_tokens") or int(tokens_in * 0.25))
        success = bool(rec.get("success", rec.get("status", "ok") not in ("error", "fail", "failed")))
        loop_i = _as_int(rec.get("loop_iteration", 1), 1)
        run_id = str(rec.get("agent_run_id") or rec.get("run_id") or f"RUN-{trace_id[:12] or span_id[:12]}")

        span_rows.append(
            {
                "span_id": span_id,
                "agent_run_id": run_id,
                "session_id": rec.get("session_id") or f"SES-{trace_id[:8]}",
                "parent_span_id": parent,
                "loop_iteration": loop_i,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "success": success,
                "trace_id": trace_id,
                "data_source": "otel",
                "capability_id": cap_id,
                "model_id": rec.get("model_id") or rec.get("gen_ai.request.model"),
                "scrubbed": True,
            }
        )

        acc = run_acc.setdefault(
            run_id,
            {
                "run_id": run_id,
                "capability_id": cap_id,
                "success": True,
                "tokens_in": 0,
                "tokens_out": 0,
                "loop_count": 0,
                "trace_id": trace_id,
                "data_source": "otel",
            },
        )
        acc["tokens_in"] += tokens_in
        acc["tokens_out"] += tokens_out
        acc["loop_count"] = max(acc["loop_count"], loop_i)
        acc["success"] = acc["success"] and success
        if cap_id != "CAP-000":
            acc["capability_id"] = cap_id

    spans = pd.DataFrame(span_rows, columns=SPANS_COLUMNS) if span_rows else pd.DataFrame(columns=SPANS_COLUMNS)
    runs = pd.DataFrame(list(run_acc.values()), columns=RUNS_COLUMNS) if run_acc else pd.DataFrame(columns=RUNS_COLUMNS)
    return {"spans": spans, "runs": runs, "agent_runs": runs.rename(columns={"run_id": "agent_run_id"}) if not runs.empty else runs}
