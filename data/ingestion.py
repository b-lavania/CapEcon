"""Batch OTEL ingest into methodology measurement tables."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from data.otel_mock_generator import generate_otel_traces


def ingest_otel_into_agentic(
    agentic: dict[str, pd.DataFrame],
    profile: dict[str, Any],
    *,
    seed: int = 42,
    otel_path: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Merge OTEL trace spans into agent_runs/spans tables.
    Generates mock traces when path missing; scrubs prompt bodies (metadata only).
    """
    from data.adapters.otel import ingest_otel_export
    from data.adapters.scrub import span_has_content

    path = Path(otel_path or "data/mock_traces.jsonl")
    if not path.exists():
        generate_otel_traces(profile, seed=seed, output_path=path)

    tables = ingest_otel_export(path)
    spans_df = tables["spans"]
    if spans_df.empty:
        return agentic
    for rec in spans_df.to_dict(orient="records"):
        if span_has_content(rec):
            raise ValueError("OTel ingest produced spans with prompt/content fields")

    rng = np.random.default_rng(seed)
    seats = agentic["seats"]
    runs = agentic["runs"]
    if runs.empty:
        agentic["spans"] = spans_df
        return agentic

    # Join adapter spans onto existing synthetic runs so seat/account joins survive.
    span_rows: list[dict[str, Any]] = []
    run_updates: dict[str, dict[str, Any]] = {}
    for rec in spans_df.to_dict(orient="records"):
        cap_id = rec.get("capability_id", "CAP-000")
        existing = runs[runs["capability_id"] == cap_id] if "capability_id" in runs.columns else runs
        if len(existing):
            run_id = existing.iloc[int(rng.integers(0, len(existing)))]["run_id"]
        else:
            run_id = runs.iloc[int(rng.integers(0, len(runs)))]["run_id"]
        loop_i = int(rec.get("loop_iteration") or 1)
        tokens = int(rec.get("tokens_in") or 0)
        span_rows.append(
            {
                "span_id": rec.get("span_id"),
                "agent_run_id": run_id,
                "session_id": rec.get("session_id") or f"SES-{str(rec.get('trace_id', ''))[:8]}",
                "loop_iteration": loop_i,
                "tokens_in": tokens,
                "tokens_out": int(rec.get("tokens_out") or 0),
                "success": bool(rec.get("success", True)),
                "trace_id": rec.get("trace_id"),
                "data_source": "otel",
                "scrubbed": True,
            }
        )
        run_updates[run_id] = {
            "loop_count": max(run_updates.get(run_id, {}).get("loop_count", 0), loop_i),
            "tokens_in": run_updates.get(run_id, {}).get("tokens_in", 0) + tokens,
        }

    otel_spans = pd.DataFrame(span_rows)
    existing_spans = agentic.get("spans", pd.DataFrame())
    agentic["spans"] = (
        pd.concat([existing_spans, otel_spans], ignore_index=True)
        if existing_spans is not None and len(existing_spans)
        else otel_spans
    )

    for run_id, upd in run_updates.items():
        mask = runs["run_id"] == run_id
        if mask.any():
            if "loop_count" in runs.columns:
                runs.loc[mask, "loop_count"] = upd["loop_count"]
            if "tokens_in" in runs.columns:
                runs.loc[mask, "tokens_in"] = upd["tokens_in"]

    agentic["runs"] = runs
    if not agentic.get("agent_runs", pd.DataFrame()).empty:
        agentic["agent_runs"] = runs.copy()
        agentic["agent_runs"]["agent_run_id"] = runs["run_id"]
    _ = seats  # seats used for future account join; keep signature stable
    return agentic
