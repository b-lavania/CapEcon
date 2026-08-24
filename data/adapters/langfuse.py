"""Langfuse adapter — JSON export today; optional HTTP pull when credentials exist."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pandas as pd

from data.adapters.otel import ingest_otel_records
from data.adapters.scrub import scrub_payload


def _trace_to_span_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Map a Langfuse trace/observation export onto the OTel-flat span shape."""
    rows: list[dict[str, Any]] = []
    traces = payload.get("traces") or payload.get("data") or []
    if isinstance(payload, list):
        traces = payload
    for trace in traces:
        if not isinstance(trace, dict):
            continue
        trace = scrub_payload(trace)
        trace_id = str(trace.get("id") or trace.get("traceId") or "")
        observations = trace.get("observations") or trace.get("spans") or [trace]
        for obs in observations:
            if not isinstance(obs, dict):
                continue
            obs = scrub_payload(obs)
            usage = obs.get("usage") or {}
            rows.append(
                {
                    "trace_id": trace_id or str(obs.get("traceId") or ""),
                    "span_id": str(obs.get("id") or obs.get("span_id") or ""),
                    "parent_span_id": obs.get("parentObservationId") or obs.get("parent_span_id"),
                    "capability_id": obs.get("name") or trace.get("name") or "CAP-000",
                    "tokens_used": usage.get("input") or obs.get("promptTokens") or 0,
                    "tokens_out": usage.get("output") or obs.get("completionTokens") or 0,
                    "success": (obs.get("level") or "DEFAULT") not in ("ERROR", "error"),
                    "model_id": obs.get("model") or trace.get("model"),
                    "session_id": trace.get("sessionId"),
                    "agent_run_id": trace_id,
                    "data_source": "langfuse",
                    "scrubbed": True,
                }
            )
    return rows


def ingest_langfuse_export(path: str | Path) -> dict[str, pd.DataFrame]:
    """Parse a Langfuse JSON dump (traces + observations)."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    payload: Any
    if p.suffix == ".jsonl":
        payload = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
    rows = _trace_to_span_records(payload if isinstance(payload, dict) else {"traces": payload})
    tables = ingest_otel_records(rows)
    if not tables["spans"].empty:
        tables["spans"]["data_source"] = "langfuse"
    if not tables["runs"].empty:
        tables["runs"]["data_source"] = "langfuse"
    return tables


def ingest_langfuse_project(
    base_url: str,
    api_key: str,
    *,
    limit: int = 100,
) -> dict[str, pd.DataFrame]:
    """
    Pull traces from Langfuse REST API when credentials are provided.

    Requires `httpx`. Failures raise RuntimeError with a readable message.
    """
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("httpx is required for live Langfuse pull. Use a JSON export instead.") from exc

    url = urljoin(base_url.rstrip("/") + "/", "api/public/traces")
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers=headers, params={"limit": limit})
        if resp.status_code >= 400:
            raise RuntimeError(f"Langfuse HTTP {resp.status_code}: {resp.text[:200]}")
        payload = resp.json()
    rows = _trace_to_span_records(payload if isinstance(payload, dict) else {"traces": payload})
    tables = ingest_otel_records(rows)
    if not tables["spans"].empty:
        tables["spans"]["data_source"] = "langfuse"
    return tables
