"""CSV loaders for accounts, outcomes, subscriptions, usage_events."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

TABLE_REQUIRED: dict[str, list[str]] = {
    "accounts": ["account_id"],
    "outcomes": ["outcome_id", "agent_run_id"],
    "subscriptions": ["subscription_id", "account_id"],
    "usage_events": ["usage_event_id", "account_id"],
    "approvals": ["run_id"],
    "eval_results": ["capability_id", "score"],
}


def ingest_csv_table(
    path: str | Path,
    table: str,
    *,
    column_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Load a CSV and optionally rename columns onto Workspace names."""
    df = pd.read_csv(path)
    if column_map:
        df = df.rename(columns=column_map)
    required = TABLE_REQUIRED.get(table, [])
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{table} CSV missing required columns: {missing}")
    return df


def ingest_csv_mapping(files: dict[str, str | Path], *, column_maps: dict[str, dict[str, str]] | None = None) -> dict[str, pd.DataFrame]:
    """`files` maps table name → path."""
    column_maps = column_maps or {}
    out: dict[str, pd.DataFrame] = {}
    for table, path in files.items():
        out[table] = ingest_csv_table(path, table, column_map=column_maps.get(table))
    return out
