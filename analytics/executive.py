"""Executive weekly summary — leadership-facing, not operator chrome."""

from __future__ import annotations

from typing import Any

from analytics.metrics import resolve_metric
from core.workspace import Workspace


PINNED = [
    "delegation_ratio",
    "autonomy_ratio",
    "cost_per_successful_outcome",
    "outcome_success_drift",
    "contribution_margin_nrr",
    "human_intervention_rate",
    "eval_score_delta",
    "trust_incident_rate",
]


def top_decisions(records: list[dict[str, Any]], n: int = 5) -> list[dict[str, Any]]:
    ranked = sorted(
        records,
        key=lambda r: -float((r.get("economics") or {}).get("primary_metric_usd") or 0),
    )
    return ranked[:n]


def claim_type_of(record: dict[str, Any]) -> str:
    if record.get("evidence", {}).get("claim_type"):
        return record["evidence"]["claim_type"]
    for exc in record.get("exceptions") or []:
        ct = (exc.get("evidence") or {}).get("claim_type")
        if ct:
            return ct
    return "associational"


def mean_surplus_usd(records: list[dict[str, Any]]) -> float | None:
    vals = [
        float((r.get("economics") or {}).get("surplus_usd"))
        for r in records
        if (r.get("economics") or {}).get("surplus_usd") is not None
    ]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def executive_summary(workspace: Workspace, records: list[dict[str, Any]]) -> dict[str, Any]:
    pins = []
    for name in PINNED:
        try:
            pins.append(resolve_metric(name, workspace))
        except Exception:
            pins.append({"name": name, "display": "—", "value": None})
    top = top_decisions(records, 5)
    surplus_mean = mean_surplus_usd(records)
    return {
        "headline": f"{len(top)} decision(s) worth leadership time this week",
        "pins": pins,
        "mean_surplus_usd": surplus_mean,
        "top_decisions": [
            {
                "record_id": r.get("record_id"),
                "subject": r.get("subject"),
                "verdict": r.get("decision", {}).get("verdict"),
                "action": r.get("decision", {}).get("recommended_action"),
                "cost_usd": r.get("economics", {}).get("primary_metric_usd"),
                "surplus_usd": (r.get("economics") or {}).get("surplus_usd"),
                "claim_type": claim_type_of(r),
                "rationale": r.get("decision", {}).get("rationale", ""),
            }
            for r in top
        ],
        "claim_disclaimer": "Simulated / associational / causal — see evidence.claim_type on every number.",
    }


def slack_blocks(summary: dict[str, Any]) -> dict[str, Any]:
    lines = [f"*{summary['headline']}*"]
    for d in summary.get("top_decisions") or []:
        surplus = d.get("surplus_usd")
        surplus_txt = f" · surplus {surplus:+.2f}/outcome" if surplus is not None else ""
        lines.append(
            f"• `{d.get('verdict')}` → *{d.get('action')}* (${d.get('cost_usd') or 0:,.0f}{surplus_txt}) "
            f"[{d.get('claim_type')}]"
        )
    return {"text": "\n".join(lines), "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}]}


def markdown_report(summary: dict[str, Any]) -> str:
    parts = ["# churnOS weekly", "", summary.get("headline", ""), "", "## Metrics", ""]
    for p in summary.get("pins") or []:
        parts.append(f"- **{p.get('label', p.get('name'))}:** {p.get('display', '—')}")
    parts += ["", "## Decisions", ""]
    for d in summary.get("top_decisions") or []:
        parts.append(
            f"- **{d.get('action')}** ({d.get('verdict')}) — ${d.get('cost_usd') or 0:,.0f} "
            f"— claim `{d.get('claim_type')}`"
        )
        if d.get("rationale"):
            parts.append(f"  - {d['rationale'][:240]}")
    parts += ["", f"_{summary.get('claim_disclaimer')}_", ""]
    return "\n".join(parts)
