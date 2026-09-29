"""Macro period adapter: EconAgent / LLM-Economist-shaped aggregates → outcomes + usage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from data.adapters.base import (
    OUTCOMES_COLUMNS,
    USAGE_COLUMNS,
    align_frame,
    as_bool,
    as_float,
    load_json_or_jsonl,
    stamp_provenance,
)


def ingest_macro_export(path: str | Path) -> dict[str, Any]:
    records = load_json_or_jsonl(path)
    return ingest_macro_records(records)


def ingest_macro_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    outcome_rows: list[dict[str, Any]] = []
    usage_rows: list[dict[str, Any]] = []
    for i, rec in enumerate(records):
        period = str(rec.get("period_id") or rec.get("outcome_id") or f"PERIOD-{i:04d}")
        account = str(rec.get("account_id") or rec.get("region_id") or f"MACRO-{i:03d}")
        value = as_float(rec.get("outcome_value_usd") or rec.get("aggregate_output_usd"), 0.0)
        cost = as_float(rec.get("cost_usd") or rec.get("agent_cost_usd"), 0.0)
        occurred = rec.get("occurred_at") or rec.get("period_end") or "2026-01-01T00:00:00Z"
        run_id = str(rec.get("agent_run_id") or f"MACRO-RUN-{i:04d}")
        success = as_bool(rec.get("success"), value > 0)
        outcome_rows.append(
            {
                "outcome_id": period,
                "account_id": account,
                "end_user_id": str(rec.get("end_user_id") or account),
                "agent_run_id": run_id,
                "outcome_type": str(rec.get("outcome_type") or "macro_period"),
                "success": success,
                "verified": as_bool(rec.get("verified"), True),
                "verified_by": "deterministic_stage",
                "occurred_at": occurred,
                "days_since_signup": int(rec.get("days_since_signup") or 0),
                "outcome_value_usd": value,
                "list_price_per_outcome_usd": None,
            }
        )
        usage_rows.append(
            {
                "usage_event_id": f"USE-{period}",
                "account_id": account,
                "agent_run_id": run_id,
                "tokens_in": int(rec.get("tokens_in") or 0),
                "tokens_out": int(rec.get("tokens_out") or 0),
                "cost_usd": cost,
                "recorded_at": occurred,
            }
        )
    return {
        "tables": {
            "outcomes": align_frame(outcome_rows, OUTCOMES_COLUMNS),
            "usage_events": align_frame(usage_rows, USAGE_COLUMNS),
        },
        "meta": stamp_provenance("macro", claim_type="simulated"),
    }
