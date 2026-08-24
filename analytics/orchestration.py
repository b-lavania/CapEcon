"""Multi-agent handoff, coordination cost, subgraph GDRs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from analytics.commercial import attach_commercial
from analytics.price_block import fill_price_block, primary_metric_label
from core.workspace import Workspace
from ontology.decision_rules import build_rule_trace, load_rules_for_vertical, resolve_action, resolve_verdict
from ontology.exception_taxonomy import get_category


def build_handoff_table(ws: Workspace) -> pd.DataFrame:
    """
    Sequential capability changes per seat as a teaching proxy for A→B handoffs.

    Columns: from_capability_id, to_capability_id, n, fail_count, retry_mean, cost_usd.
    """
    runs = ws.runs
    cols = [
        "from_capability_id",
        "to_capability_id",
        "n",
        "fail_count",
        "success_rate",
        "retry_mean",
        "cost_usd",
    ]
    if runs.empty or "capability_id" not in runs.columns or "seat_id" not in runs.columns:
        return pd.DataFrame(columns=cols)

    df = runs.sort_values(["seat_id", "started_at"] if "started_at" in runs.columns else ["seat_id"]).copy()
    df["prev_cap"] = df.groupby("seat_id")["capability_id"].shift(1)
    edges = df[df["prev_cap"].notna() & (df["prev_cap"] != df["capability_id"])]
    if edges.empty:
        return pd.DataFrame(columns=cols)

    retry = "loop_count" if "loop_count" in edges.columns else None
    cost_col = "run_cost_usd" if "run_cost_usd" in edges.columns else None
    agg: dict[str, Any] = {
        "n": ("capability_id", "count"),
        "fail_count": ("success", lambda s: int((~s.astype(bool)).sum()) if len(s) else 0),
        "success_rate": ("success", "mean"),
    }
    if retry:
        agg["retry_mean"] = (retry, "mean")
    if cost_col:
        agg["cost_usd"] = (cost_col, "sum")
    grouped = (
        edges.groupby(["prev_cap", "capability_id"], as_index=False)
        .agg(**agg)
        .rename(columns={"prev_cap": "from_capability_id", "capability_id": "to_capability_id"})
    )
    if "retry_mean" not in grouped.columns:
        grouped["retry_mean"] = 1.0
    if "cost_usd" not in grouped.columns:
        grouped["cost_usd"] = 0.0
    return grouped


def handoff_success_rate(ws: Workspace) -> float:
    table = build_handoff_table(ws)
    if table.empty:
        return 0.0
    return float(table["success_rate"].mean() * 100)


def coordination_cost_ratio(ws: Workspace) -> float:
    """Share of run cost attributed to multi-capability sequences vs all run cost."""
    table = build_handoff_table(ws)
    total = float(ws.runs["run_cost_usd"].sum()) if not ws.runs.empty and "run_cost_usd" in ws.runs.columns else 0.0
    if total <= 0:
        if ws.runs.empty or "coordination_token_share" not in ws.runs.columns:
            return 0.0
        return float(ws.runs["coordination_token_share"].mean() * 100)
    coord = float(table["cost_usd"].sum()) if not table.empty else 0.0
    return coord / total * 100


def retry_amplification(ws: Workspace) -> float:
    from analytics.challenge_metrics import retry_amplification_factor

    return float(retry_amplification_factor(ws))


def orphaned_subtask_rate(ws: Workspace) -> float:
    runs = ws.runs
    if runs.empty:
        return 0.0
    if "success" in runs.columns and "loop_count" in runs.columns:
        max_loops = float(ws.profile.get("max_loops_threshold", 8))
        orphan = (~runs["success"].astype(bool)) & (runs["loop_count"] >= max_loops)
        return float(orphan.mean() * 100)
    return float((~runs["success"].astype(bool)).mean() * 100) if "success" in runs.columns else 0.0


def trust_boundary_violations(ws: Workspace) -> float:
    """Connectors used by a capability that are not in the capability's declared tool set — proxy via fail rate * unknown connectors."""
    graph = getattr(ws, "connector_capability_graph", pd.DataFrame())
    if graph is None or graph.empty:
        return 0.0
    if "fail_count" not in graph.columns or "call_count" not in graph.columns:
        return 0.0
    fail_rate = graph["fail_count"] / graph["call_count"].clip(lower=1)
    return float((fail_rate > 0.35).mean() * 100)


def blast_radius_top(ws: Workspace, n: int = 5) -> pd.DataFrame:
    graph = getattr(ws, "connector_capability_graph", pd.DataFrame())
    if graph is None or graph.empty:
        return pd.DataFrame()
    return graph.sort_values("blast_radius_seats", ascending=False).head(n)


def emit_subgraph_records(ws: Workspace, *, semantics_overlay: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Workflow-level GDRs from handoff / coordination / orphan signals."""
    semantics = load_rules_for_vertical("orchestration", overlay=semantics_overlay)
    table = build_handoff_table(ws)
    records: list[dict[str, Any]] = []
    ws_id = ws.workspaces["workspace_id"].iloc[0] if len(ws.workspaces) else "WS-0000"
    acc_id = str(ws.accounts["account_id"].iloc[0]) if len(getattr(ws, "accounts", [])) else "ACC-000"

    def _exc(category: str, title: str, cost: float, cap_id: str) -> dict[str, Any]:
        meta = get_category(category)
        return {
            "exception_id": f"exc_orch_{category}_{cap_id}",
            "category": category,
            "title": title,
            "description": meta["playbook_hint"],
            "confidence": 0.7,
            "rank": 1,
            "severity": meta["default_severity"],
            "owner": meta["owner_role"],
            "impact": {"cost_usd": float(cost)},
            "capability_id": cap_id,
        }

    exceptions: list[dict[str, Any]] = []
    if not table.empty:
        worst = table.sort_values("success_rate").iloc[0]
        if float(worst["success_rate"]) < 0.75:
            cap = str(worst["from_capability_id"])
            exceptions.append(
                _exc(
                    "handoff_failure",
                    f"{worst['from_capability_id']} → {worst['to_capability_id']} success {worst['success_rate']:.0%}",
                    float(worst["cost_usd"]),
                    cap,
                )
            )
    if orphaned_subtask_rate(ws) > 8:
        cap = str(ws.capabilities["capability_id"].iloc[0]) if len(ws.capabilities) else "CAP-000"
        exceptions.append(_exc("orphaned_subtask", "Orphaned subtasks above 8%", 2500, cap))
    if coordination_cost_ratio(ws) > 35:
        cap = str(ws.capabilities["capability_id"].iloc[0]) if len(ws.capabilities) else "CAP-000"
        exceptions.append(_exc("coordination_cost", "Coordination cost ratio above 35%", 1800, cap))
    if trust_boundary_violations(ws) > 20:
        cap = str(ws.capabilities["capability_id"].iloc[0]) if len(ws.capabilities) else "CAP-000"
        exceptions.append(_exc("trust_boundary", "Connector fail-rate cluster looks like a trust-boundary leak", 1200, cap))

    if not exceptions:
        return []

    by_cap: dict[str, list] = {}
    for e in exceptions:
        by_cap.setdefault(e["capability_id"], []).append(e)

    src = (ws.meta or {}).get("data_source", "synthetic")
    claim = "simulated" if src in ("synthetic", None, "") else "associational"

    records: list[dict[str, Any]] = []
    for i, (cap_id, excs) in enumerate(by_cap.items(), start=1):
        verdict = resolve_verdict(excs, semantics)
        decision = resolve_action(verdict, semantics)
        decision["rule_trace"] = build_rule_trace(excs, semantics, verdict, decision)
        cost = sum(e["impact"]["cost_usd"] for e in excs)
        economics: dict[str, Any] = fill_price_block(
            {
                "primary_metric_usd": round(cost, 2),
                "primary_metric_label": primary_metric_label(semantics),
                "currency": "USD",
            },
            semantics=semantics,
            profile=ws.profile,
            workspace=ws,
            capability_id=str(cap_id),
        )
        attach_commercial(
            decision, economics, semantics=semantics, workspace=ws, profile=ws.profile
        )
        records.append(
            {
                "record_id": f"gdr_subgraph_{i:04d}",
                "vertical": "orchestration",
                "schema_version": "1.0.0",
                "ontology_version": "orchestration_v1",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "evaluator_id": "subgraph_health",
                "subject": {
                    "entity_type": "workflow",
                    "workspace_id": ws_id,
                    "capability_id": cap_id,
                    "account_id": acc_id,
                    "assist_type": "multi_agent",
                },
                "exceptions": excs,
                "economics": economics,
                "decision": decision,
                "evidence": {"claim_type": claim, "n": int(table["n"].sum()) if not table.empty else 0},
            }
        )
    records.sort(key=lambda r: -r["economics"]["primary_metric_usd"])
    return records
