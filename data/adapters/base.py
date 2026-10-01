"""Shared helpers for CapEcon econ-world ingest adapters.

Adapters accept a local file or in-memory export and emit Workspace table
frames. They never call upstream simulators at runtime.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from data.adapters.scrub import scrub_payload

EVALUATOR_IDS = {
    "market": "capecon_market_adapter",
    "workflow": "capecon_workflow_adapter",
    "rl": "capecon_rl_adapter",
    "macro": "capecon_macro_adapter",
    "abm": "capecon_abm_adapter",
    "finance": "capecon_finance_adapter",
    "token_econ": "capecon_token_econ_adapter",
}

INGEST_SOURCES = frozenset(
    {"uploaded", "otel", "langfuse", "vision", "market", "workflow", "rl", "macro", "abm", "finance", "token_econ"}
)

RUNS_COLUMNS = [
    "run_id",
    "seat_id",
    "capability_id",
    "capability_version_id",
    "started_at",
    "success",
    "run_cost_usd",
    "trust_incident",
]

OUTCOMES_COLUMNS = [
    "outcome_id",
    "account_id",
    "end_user_id",
    "agent_run_id",
    "outcome_type",
    "success",
    "verified",
    "verified_by",
    "occurred_at",
    "days_since_signup",
    "outcome_value_usd",
    "list_price_per_outcome_usd",
]

SPANS_COLUMNS = [
    "span_id",
    "agent_run_id",
    "session_id",
    "loop_iteration",
    "tokens_in",
    "tokens_out",
    "success",
]

USAGE_COLUMNS = [
    "usage_event_id",
    "account_id",
    "agent_run_id",
    "tokens_in",
    "tokens_out",
    "cost_usd",
    "recorded_at",
]

ACCOUNTS_COLUMNS = [
    "account_id",
    "tier",
    "pricing_model",
    "onboarding_completed",
    "created_at",
]

AGENT_TXN_COLUMNS = [
    "transaction_id",
    "occurred_at",
    "seller_id",
    "buyer_id",
    "capability_id",
    "agent_run_id",
    "gmv_usd",
    "take_rate",
    "platform_revenue_usd",
    "agent_inference_cost_usd",
    "agent_assist_type",
    "verified",
    "verified_by",
    "success",
]

ROUTING_COLUMNS = [
    "run_id",
    "router_model",
    "selected_tier",
    "prompt_tokens",
    "completion_tokens",
    "cached_tokens",
    "cost_usd",
    "latency_ms",
    "cache_hit",
    "cascade_step_index",
    "verification_status",
    "recorded_at",
]


def stamp_provenance(
    category: str,
    *,
    claim_type: str = "simulated",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return meta stamped onto adapter results and workspace ingest."""
    meta = {
        "ingest_source": category,
        "adapter_id": f"{category}_adapter",
        "evaluator_id": EVALUATOR_IDS[category],
        "claim_type": claim_type,
    }
    if extra:
        meta.update(extra)
    return meta


def align_frame(rows: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    """Build a DataFrame with the expected columns (missing cols filled None)."""
    if not rows:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(rows)
    for col in columns:
        if col not in frame.columns:
            frame[col] = None
    extras = [c for c in frame.columns if c not in columns]
    return frame[columns + extras]


def scrub_record(rec: dict[str, Any]) -> dict[str, Any]:
    return scrub_payload(dict(rec))


def load_json_or_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Load a JSON array, a single JSON object, or JSONL into a list of dicts."""
    p = Path(path)
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        return [scrub_record(r) for r in data if isinstance(r, dict)]
    if text.startswith("{"):
        # Single object or NDJSON starting with {
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return [scrub_record(obj)]
            if isinstance(obj, list):
                return [scrub_record(r) for r in obj if isinstance(r, dict)]
        except json.JSONDecodeError:
            pass
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if isinstance(rec, dict):
            rows.append(scrub_record(rec))
    return rows


def as_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in ("1", "true", "yes", "y"):
        return True
    if s in ("0", "false", "no", "n"):
        return False
    return default
