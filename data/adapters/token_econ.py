"""RouteLLM / FrugalGPT cascade routing telemetry → runs + usage_events + routing_log."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from data.adapters.base import (
    ROUTING_COLUMNS,
    RUNS_COLUMNS,
    USAGE_COLUMNS,
    align_frame,
    as_bool,
    as_float,
    load_json_or_jsonl,
    stamp_provenance,
)


def ingest_token_econ_export(path: str | Path) -> dict[str, Any]:
    records = load_json_or_jsonl(path)
    return ingest_token_econ_records(records)


def ingest_token_econ_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    run_rows: list[dict[str, Any]] = []
    usage_rows: list[dict[str, Any]] = []
    routing_rows: list[dict[str, Any]] = []

    for i, rec in enumerate(records):
        query_id = str(rec.get("query_id") or rec.get("run_id") or f"TOKEC-{i:04d}")
        router_mdl = str(rec.get("router_model") or "unknown_router")
        tier = str(rec.get("selected_tier") or "standard")
        p_tokens = int(rec.get("prompt_tokens") or rec.get("tokens_in") or 0)
        c_tokens = int(rec.get("completion_tokens") or rec.get("tokens_out") or 0)
        cached = int(rec.get("cached_tokens") or 0)
        cost = as_float(rec.get("cost_usd") or rec.get("run_cost_usd"), 0.0)
        latency = as_float(rec.get("latency_ms"), 0.0)
        cache_hit = as_bool(rec.get("cache_hit"), cached > 0)
        cascade_idx = int(rec.get("cascade_step_index") or 0)
        verified = str(rec.get("verification_status") or "unverified")
        recorded = rec.get("recorded_at") or rec.get("started_at") or "2026-01-01T00:00:00Z"
        success = as_bool(rec.get("success"), verified in ("verified", "passed", "accepted"))

        run_rows.append(
            {
                "run_id": query_id,
                "seat_id": str(rec.get("seat_id") or "router"),
                "capability_id": router_mdl,
                "capability_version_id": f"{router_mdl}:{tier}",
                "started_at": recorded,
                "success": success,
                "run_cost_usd": cost,
                "trust_incident": False,
            }
        )
        routing_rows.append(
            {
                "run_id": query_id,
                "router_model": router_mdl,
                "selected_tier": tier,
                "prompt_tokens": p_tokens,
                "completion_tokens": c_tokens,
                "cached_tokens": cached,
                "cost_usd": cost,
                "latency_ms": latency,
                "cache_hit": cache_hit,
                "cascade_step_index": cascade_idx,
                "verification_status": verified,
                "recorded_at": recorded,
            }
        )
        usage_rows.append(
            {
                "usage_event_id": f"USE-{query_id}",
                "account_id": str(rec.get("account_id") or "default"),
                "agent_run_id": query_id,
                "tokens_in": p_tokens,
                "tokens_out": c_tokens,
                "cost_usd": cost,
                "recorded_at": recorded,
            }
        )

    return {
        "tables": {
            "runs": align_frame(run_rows, RUNS_COLUMNS),
            "usage_events": align_frame(usage_rows, USAGE_COLUMNS),
            "routing_log": align_frame(routing_rows, ROUTING_COLUMNS),
        },
        "meta": stamp_provenance("token_econ", claim_type="associational"),
    }
