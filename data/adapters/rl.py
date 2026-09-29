"""RL episode adapter: Econojax / AI Economist-shaped logs → runs with reward."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from data.adapters.base import (
    RUNS_COLUMNS,
    align_frame,
    as_bool,
    as_float,
    load_json_or_jsonl,
    stamp_provenance,
)


def ingest_rl_export(path: str | Path) -> dict[str, Any]:
    records = load_json_or_jsonl(path)
    return ingest_rl_records(records)


def ingest_rl_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    run_rows: list[dict[str, Any]] = []
    for i, rec in enumerate(records):
        run_id = str(rec.get("run_id") or rec.get("episode_id") or f"RL-{i:04d}")
        cost = as_float(rec.get("run_cost_usd") or rec.get("compute_cost_usd"), 0.0)
        reward = as_float(rec.get("reward"), 0.0)
        steps = int(rec.get("n_steps") or rec.get("steps") or 0)
        started = rec.get("started_at") or "2026-01-01T00:00:00Z"
        run_rows.append(
            {
                "run_id": run_id,
                "seat_id": str(rec.get("seat_id") or rec.get("agent_id") or f"agent-{i}"),
                "capability_id": str(rec.get("capability_id") or rec.get("policy_id") or "rl_policy"),
                "capability_version_id": str(rec.get("capability_version_id") or "rl_policy:v1"),
                "started_at": started,
                "success": as_bool(rec.get("success"), reward > 0),
                "run_cost_usd": cost,
                "trust_incident": False,
                "reward": reward,
                "n_steps": steps,
            }
        )
    return {
        "tables": {"runs": align_frame(run_rows, RUNS_COLUMNS)},
        "meta": stamp_provenance("rl", claim_type="simulated"),
    }
