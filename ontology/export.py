"""CSV export adapter for GrowthDecisionRecords (P7)."""

from __future__ import annotations

import csv
import io
from typing import Any


def records_to_csv(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    buf = io.StringIO()
    fieldnames = [
        "record_id", "vertical", "verdict", "recommended_action", "final_action",
        "primary_metric_usd", "floor_usd", "value_usd", "surplus_usd",
        "task_tier", "commercial_action", "capability_id",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in records:
        writer.writerow({
            "record_id": r.get("record_id"),
            "vertical": r.get("vertical"),
            "verdict": r.get("decision", {}).get("verdict"),
            "recommended_action": r.get("decision", {}).get("recommended_action"),
            "final_action": r.get("decision", {}).get("final_action"),
            "primary_metric_usd": r.get("economics", {}).get("primary_metric_usd"),
            "floor_usd": r.get("economics", {}).get("floor_usd"),
            "value_usd": r.get("economics", {}).get("value_usd"),
            "surplus_usd": r.get("economics", {}).get("surplus_usd"),
            "task_tier": r.get("subject", {}).get("task_tier"),
            "commercial_action": r.get("decision", {}).get("commercial_action"),
            "capability_id": r.get("subject", {}).get("capability_id"),
        })
    return buf.getvalue()
