"""ABM scenario adapter: HARK / scikit-agent-shaped summaries → accounts, outcomes, usage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from data.adapters.base import (
    ACCOUNTS_COLUMNS,
    OUTCOMES_COLUMNS,
    USAGE_COLUMNS,
    align_frame,
    as_bool,
    as_float,
    load_json_or_jsonl,
    stamp_provenance,
)


def ingest_abm_export(path: str | Path) -> dict[str, Any]:
    records = load_json_or_jsonl(path)
    return ingest_abm_records(records)


def ingest_abm_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    account_rows: list[dict[str, Any]] = []
    outcome_rows: list[dict[str, Any]] = []
    usage_rows: list[dict[str, Any]] = []
    for i, rec in enumerate(records):
        account = str(rec.get("account_id") or rec.get("household_id") or f"ABM-{i:03d}")
        created = rec.get("created_at") or rec.get("scenario_start") or "2026-01-01T00:00:00Z"
        value = as_float(rec.get("outcome_value_usd") or rec.get("welfare_proxy_usd"), 0.0)
        runtime = as_float(rec.get("runtime_cost_usd") or rec.get("cost_usd"), 0.0)
        occurred = rec.get("occurred_at") or rec.get("scenario_end") or created
        run_id = str(rec.get("agent_run_id") or f"ABM-RUN-{i:04d}")
        account_rows.append(
            {
                "account_id": account,
                "tier": str(rec.get("tier") or "standard"),
                "pricing_model": str(rec.get("pricing_model") or "simulated"),
                "onboarding_completed": as_bool(rec.get("onboarding_completed"), True),
                "created_at": created,
            }
        )
        outcome_rows.append(
            {
                "outcome_id": f"OUT-ABM-{i:04d}",
                "account_id": account,
                "end_user_id": account,
                "agent_run_id": run_id,
                "outcome_type": str(rec.get("outcome_type") or "abm_scenario"),
                "success": as_bool(rec.get("success"), True),
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
                "usage_event_id": f"USE-ABM-{i:04d}",
                "account_id": account,
                "agent_run_id": run_id,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_usd": runtime,
                "recorded_at": occurred,
            }
        )
    return {
        "tables": {
            "accounts": align_frame(account_rows, ACCOUNTS_COLUMNS),
            "outcomes": align_frame(outcome_rows, OUTCOMES_COLUMNS),
            "usage_events": align_frame(usage_rows, USAGE_COLUMNS),
        },
        "meta": stamp_provenance("abm", claim_type="simulated"),
    }
