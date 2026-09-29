"""Finance blotter adapter: TwinMarket-shaped trades → runs + outcomes (PnL, latency)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from data.adapters.base import (
    OUTCOMES_COLUMNS,
    RUNS_COLUMNS,
    align_frame,
    as_bool,
    as_float,
    load_json_or_jsonl,
    stamp_provenance,
)


def ingest_finance_export(path: str | Path) -> dict[str, Any]:
    records = load_json_or_jsonl(path)
    return ingest_finance_records(records)


def ingest_finance_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    run_rows: list[dict[str, Any]] = []
    outcome_rows: list[dict[str, Any]] = []
    for i, rec in enumerate(records):
        run_id = str(rec.get("run_id") or rec.get("trade_id") or f"FIN-{i:04d}")
        cost = as_float(rec.get("run_cost_usd") or rec.get("compute_cost_usd"), 0.0)
        pnl = as_float(rec.get("pnl_usd") or rec.get("outcome_value_usd"), 0.0)
        latency = rec.get("latency_ms")
        started = rec.get("started_at") or rec.get("occurred_at") or "2026-01-01T00:00:00Z"
        account = str(rec.get("account_id") or rec.get("strategy_id") or f"STRAT-{i:03d}")
        success = as_bool(rec.get("success"), pnl >= 0)
        run_row: dict[str, Any] = {
            "run_id": run_id,
            "seat_id": str(rec.get("seat_id") or account),
            "capability_id": str(rec.get("capability_id") or rec.get("strategy_id") or "finance_strategy"),
            "capability_version_id": str(rec.get("capability_version_id") or "finance_strategy:v1"),
            "started_at": started,
            "success": success,
            "run_cost_usd": cost,
            "trust_incident": False,
        }
        if latency is not None:
            run_row["latency_ms"] = int(as_float(latency, 0))
        run_rows.append(run_row)
        outcome_rows.append(
            {
                "outcome_id": f"OUT-{run_id}",
                "account_id": account,
                "end_user_id": account,
                "agent_run_id": run_id,
                "outcome_type": str(rec.get("outcome_type") or "trade"),
                "success": success,
                "verified": as_bool(rec.get("verified"), True),
                "verified_by": "deterministic_stage",
                "occurred_at": started,
                "days_since_signup": int(rec.get("days_since_signup") or 0),
                "outcome_value_usd": pnl,
                "list_price_per_outcome_usd": None,
                "pnl_usd": pnl,
            }
        )
    return {
        "tables": {
            "runs": align_frame(run_rows, RUNS_COLUMNS),
            "outcomes": align_frame(outcome_rows, OUTCOMES_COLUMNS),
        },
        "meta": stamp_provenance("finance", claim_type="simulated"),
    }
