"""Vision Agent bakeoff + historic jobs — two records, never one mapping.

Bakeoff `cost_usd` is the cost of running the quoting agent (token oracle,
`estimated`). Historic `actuals.price_dollars` is what the customer paid for
the physical move. Flattening both onto one GrowthDecisionRecord is a
category error this module exists to refuse.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from analytics.price_block import fill_price_block, price_sentence
from ontology.decision_rules import resolve_action, resolve_verdict
from ontology.semantics import load_semantics
from ontology.validate import validate_record

CAPABILITY_ID = "vision_quote"
AGENT_ID = "AGT-VISION"
WORKSPACE_ID = "WS-VISION"

# Numeric summary fields only. Never copy vision item lists, notes blobs, or prompts.
_SUMMARY_KEYS = (
    "model_name",
    "runs_attempted",
    "runs_succeeded",
    "runs_failed",
    "cost_usd",
    "api_cost_usd_sum",
    "cost_pricing_as_of",
    "move_quote_usd",
    "move_quote_min_usd",
    "move_quote_max_usd",
    "item_count",
)

_DROP_SUMMARY = frozenset(
    {"items", "notes", "images", "photos", "prompt", "response", "frozen_vision", "media"}
)

_QUALITY_TO_CHARGED = {
    "trusted": "invoiced",
    "guess": "reconstructed",
    "incomplete": "reconstructed",
    "excluded": "reconstructed",
}

# Quoting agent is internal. No teaching human-estimator baseline — that
# $18.40 prior is for inbox assistants, not a 0.3¢ API call.
VISION_AGENT_PROFILE: dict[str, Any] = {
    "preset_id": "vision_quote",
    "ontology_vertical": "agent_runtime",
    "ontology_version": "agent_runtime_v1",
    "pricing_mode": "internal_budget",
    "billing_model": "internal",
    "priors": {},
}


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_json(path_or_obj: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(path_or_obj, dict):
        return path_or_obj
    return json.loads(Path(path_or_obj).read_text(encoding="utf-8"))


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ingest_vision_bakeoff(path_or_obj: str | Path | dict[str, Any]) -> dict[str, Any]:
    """Slim a bakeoff `run.json` to model summaries. Item lists never leave this function."""
    raw = _load_json(path_or_obj)
    summaries_in = raw.get("model_summaries") or {}
    summaries: dict[str, dict[str, Any]] = {}
    for name, row in summaries_in.items():
        if not isinstance(row, dict):
            continue
        slim: dict[str, Any] = {"model_name": str(row.get("model_name") or name)}
        for key in _SUMMARY_KEYS:
            if key == "model_name":
                continue
            if key in row and key not in _DROP_SUMMARY:
                slim[key] = row[key]
        summaries[str(name)] = slim
    return {
        "run_id": str(raw.get("run_id") or "unknown"),
        "created_at": raw.get("created_at"),
        "baseline_model": raw.get("baseline_model"),
        "models": list(raw.get("models") or summaries.keys()),
        "file_count": raw.get("file_count"),
        "total_api_cost_usd": _as_float(raw.get("total_api_cost_usd")),
        "honesty": (
            raw.get("honesty")
            or "token-oracle estimated cost; not a provider invoice; "
            "move_quote_* is the customer's job quote, not the agent SKU"
        ),
        "model_summaries": summaries,
    }


def ingest_vision_historic_jobs(path: str | Path) -> list[dict[str, Any]]:
    """Parse historic jobs JSONL into quote records. No agent cost on these."""
    text = Path(path).read_text(encoding="utf-8")
    jobs: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        jobs.append(_quote_record_from_job(rec))
    return jobs


def _quote_record_from_job(rec: dict[str, Any]) -> dict[str, Any]:
    actuals = rec.get("actuals") or {}
    charged = _as_float(actuals.get("price_dollars"))
    quality = str(rec.get("actuals_quality") or "guess")
    charged_basis = _QUALITY_TO_CHARGED.get(quality, "reconstructed")
    headline = bool(rec.get("include_in_headline_metrics")) and quality == "trusted"
    eval_block = rec.get("eval") or {}
    media = rec.get("media") or {}
    job_key = str(rec.get("job_key") or rec.get("name") or "unknown")
    economics: dict[str, Any] = {
        "primary_metric_usd": charged,
        "primary_metric_label": "total_quote_usd",
        "currency": "USD",
        "charged_usd": charged,
        "charged_basis": charged_basis,
    }
    pred_min = _as_float(rec.get("price_min_dollars") or (rec.get("prediction") or {}).get("price_min_dollars"))
    pred_max = _as_float(rec.get("price_max_dollars") or (rec.get("prediction") or {}).get("price_max_dollars"))
    in_band = price_in_band(charged, pred_min, pred_max)
    if pred_min is not None:
        economics["quote_band_min_usd"] = pred_min
    if pred_max is not None:
        economics["quote_band_max_usd"] = pred_max
    outcome: dict[str, Any] = {
        "actual_invoice_usd": charged,
        "actuals_quality": quality,
    }
    if rec.get("actuals_quality_reason"):
        outcome["actuals_quality_reason"] = rec["actuals_quality_reason"]
    if in_band is not None:
        outcome["price_in_band"] = in_band
    return {
        "record_id": f"move_{job_key}",
        "record_kind": "move_quote",
        "vertical": "moving",
        "schema_version": "1.0.0",
        "ontology_version": "move_quote_v1",
        "evaluated_at": _iso_now(),
        "subject": {"job_id": job_key, "entity_type": "job"},
        "economics": economics,
        "outcome": outcome,
        "include_in_headline_metrics": headline,
        "honesty": "Move invoice — not agent serving cost. Do not copy onto a GDR list_usd.",
        "inputs": {
            "movers": actuals.get("movers"),
            "work_time_minutes": actuals.get("work_time_minutes"),
            "media_count": media.get("media_count"),
            "eval_tags": eval_block.get("tags"),
        },
    }


def price_in_band(
    price: float | None,
    lo: float | None,
    hi: float | None,
) -> bool | None:
    """None when the scored band is missing — do not invent a pass."""
    if price is None or lo is None or hi is None:
        return None
    return float(lo) <= float(price) <= float(hi)


def attach_quote_predictions(
    quote_records: list[dict[str, Any]],
    predictions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach a scored-eval band onto quote records. Historic JSONL has none."""
    out: list[dict[str, Any]] = []
    for rec in quote_records:
        job_id = str((rec.get("subject") or {}).get("job_id") or "")
        pred = predictions.get(job_id) or {}
        cloned = json.loads(json.dumps(rec))
        lo = _as_float(pred.get("price_min_dollars"))
        hi = _as_float(pred.get("price_max_dollars"))
        econ = cloned.setdefault("economics", {})
        if lo is not None:
            econ["quote_band_min_usd"] = lo
        if hi is not None:
            econ["quote_band_max_usd"] = hi
        charged = _as_float(econ.get("charged_usd"))
        band = price_in_band(charged, lo, hi)
        if band is not None:
            cloned.setdefault("outcome", {})["price_in_band"] = band
        out.append(cloned)
    return out


def headline_quote_records(quote_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Trusted + include_in_headline_metrics. Job 5 guesses stay out."""
    return [
        q
        for q in quote_records
        if q.get("include_in_headline_metrics")
        and (q.get("economics") or {}).get("charged_basis") == "invoiced"
    ]


def _quote_holds_baseline_band(row: dict[str, Any], baseline: dict[str, Any]) -> bool:
    bmin = _as_float(baseline.get("move_quote_min_usd"))
    bmax = _as_float(baseline.get("move_quote_max_usd"))
    quote = _as_float(row.get("move_quote_usd"))
    if quote is not None and bmin is not None and bmax is not None and bmin <= quote <= bmax:
        return True
    smin = _as_float(row.get("move_quote_min_usd"))
    smax = _as_float(row.get("move_quote_max_usd"))
    if None not in (smin, smax, bmin, bmax) and not (smax < bmin or smin > bmax):
        return True
    return False


def cheaper_models_holding_band(bakeoff: dict[str, Any]) -> list[dict[str, Any]]:
    """Models cheaper than baseline whose candidate quote still sits in the baseline band."""
    summaries = bakeoff.get("model_summaries") or {}
    baseline_name = str(bakeoff.get("baseline_model") or next(iter(summaries), ""))
    baseline = summaries.get(baseline_name) or {}
    bcost = _as_float(baseline.get("cost_usd"))
    if bcost is None:
        return []
    found: list[dict[str, Any]] = []
    for name, row in summaries.items():
        if name == baseline_name:
            continue
        if _as_int(row.get("runs_succeeded")) <= 0:
            continue
        cost = _as_float(row.get("cost_usd"))
        if cost is None or cost >= bcost:
            continue
        if not _quote_holds_baseline_band(row, baseline):
            continue
        found.append(
            {
                "model_name": name,
                "cost_usd": cost,
                "move_quote_usd": _as_float(row.get("move_quote_usd")),
                "savings_usd": round(bcost - cost, 6),
            }
        )
    found.sort(key=lambda r: r["cost_usd"])
    return found


def refuse_mixed_units(agent_gdr: dict[str, Any], quote_records: list[dict[str, Any]]) -> None:
    """Raise if a move invoice landed on the agent GDR or an API cost landed on a quote."""
    econ = agent_gdr.get("economics") or {}
    if "list_usd" in econ:
        raise ValueError("agent GDR must not carry list_usd — quoting agent is internal_budget")
    label = str(econ.get("primary_metric_label") or "")
    if label in {"total_quote_usd", "move_quote_usd"}:
        raise ValueError(f"agent GDR used a move-quote metric ({label})")
    floor = _as_float(econ.get("floor_usd")) or 0.0
    if floor >= 1.0:
        raise ValueError(f"agent floor ${floor} looks like a move invoice, not API cost")
    charged_values = []
    for quote in quote_records:
        qe = quote.get("economics") or {}
        charged = _as_float(qe.get("charged_usd"))
        if charged is not None:
            charged_values.append(charged)
        if charged is not None and charged < 1:
            raise ValueError("quote charged_usd looks like agent API cost, not a move invoice")
        q_floor = _as_float(qe.get("floor_usd"))
        if q_floor is not None and q_floor < 1:
            raise ValueError("quote record carries an agent API floor")
        if _as_float(econ.get("list_usd")) is not None and charged is not None:
            if abs(float(econ["list_usd"]) - charged) < 1e-6:
                raise ValueError("agent list_usd equals a move charged_usd — category error")
    if floor > 0 and charged_values:
        for charged in charged_values:
            if abs(floor - charged) < 1.0:
                raise ValueError("agent floor matches a move invoice within $1 — category error")


def bakeoff_to_tables(bakeoff: dict[str, Any]) -> dict[str, pd.DataFrame]:
    """Workspace join tables. Agent API cost only — no move invoices as outcomes."""
    run_id = str(bakeoff.get("run_id") or "unknown")
    created = bakeoff.get("created_at")
    run_rows: list[dict[str, Any]] = []
    usage_rows: list[dict[str, Any]] = []
    for name, row in (bakeoff.get("model_summaries") or {}).items():
        rid = f"VIS-{run_id}-{name}"
        cost = _as_float(row.get("cost_usd")) or 0.0
        succeeded = _as_int(row.get("runs_succeeded")) > 0
        run_rows.append(
            {
                "run_id": rid,
                "capability_id": CAPABILITY_ID,
                "success": succeeded,
                "run_cost_usd": cost,
                "model_id": name,
                "data_source": "vision",
                "tokens_in": 0,
                "tokens_out": 0,
                "loop_count": 1,
                "trace_id": run_id,
            }
        )
        usage_rows.append(
            {
                "usage_event_id": f"USE-{rid}",
                "account_id": WORKSPACE_ID,
                "agent_run_id": rid,
                "cost_usd": cost,
                "cost_basis": "estimated",
                "cost_pricing_as_of": row.get("cost_pricing_as_of"),
                "recorded_at": created,
            }
        )
    return {
        "runs": pd.DataFrame(run_rows),
        "usage_events": pd.DataFrame(usage_rows),
    }


def compose_vision_records(
    bakeoff: dict[str, Any],
    quote_records: list[dict[str, Any]] | None = None,
    *,
    profile: dict[str, Any] | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Agent GDR from bakeoff cost; quote records from historic invoices. Separate units."""
    profile = profile or VISION_AGENT_PROFILE
    quotes = list(quote_records or [])
    summaries = bakeoff.get("model_summaries") or {}
    baseline_name = str(bakeoff.get("baseline_model") or next(iter(summaries), ""))
    baseline = summaries.get(baseline_name) or {}
    baseline_cost = _as_float(baseline.get("cost_usd"))
    succeeded = _as_int(baseline.get("runs_succeeded"))
    n_verified = 1 if succeeded > 0 and baseline_cost is not None else 0
    production = baseline_cost if n_verified else 0.0

    cheaper = cheaper_models_holding_band(bakeoff)
    cheapest = cheaper[0] if cheaper else None
    savings = float(cheapest["savings_usd"]) if cheapest else 0.0

    exceptions: list[dict[str, Any]] = []
    if cheapest:
        exceptions.append(
            {
                "exception_id": "exc_vision_reallocate",
                "category": "run_cost_blowout",
                "title": "Cheaper model holds the quote band",
                "description": (
                    f"{cheapest['model_name']} produces a quote inside the baseline band "
                    f"at ${cheapest['cost_usd']:.4f} vs {baseline_name} ${baseline_cost:.4f}."
                ),
                "confidence": 0.7,
                "rank": 1,
                "severity": "medium",
                "owner": "platform",
                "blocks_subject": False,
                "blocked_entity": {"entity_type": "capability", "entity_id": CAPABILITY_ID},
                "impact": {"cost_usd": round(savings, 6)},
            }
        )

    semantics = load_semantics("agent_runtime")
    verdict = resolve_verdict(exceptions, semantics)
    decision = resolve_action(verdict, semantics)

    breakdown = [
        {
            "label": name,
            "amount_usd": round(float(row.get("cost_usd") or 0), 6),
            "notes": "token-oracle estimated API $",
        }
        for name, row in summaries.items()
    ]
    ranking = round(savings, 6) if cheapest else round(float(production or 0), 6)
    economics = fill_price_block(
        {
            "primary_metric_usd": ranking,
            "primary_metric_label": "cost_of_leaving_live_usd",
            "currency": "USD",
            "breakdown": breakdown,
        },
        semantics=semantics,
        profile=profile,
        n_verified=n_verified,
        production_usd=production,
        cost_basis="estimated",
    )
    evaluated_at = bakeoff.get("created_at") or _iso_now()
    pricing_as_of = baseline.get("cost_pricing_as_of")
    evidence: dict[str, Any] = {
        "claim_type": "associational",
        "n": n_verified,
        "caption": (
            f"Bakeoff {bakeoff.get('run_id')} token oracle"
            + (f"; pricing as of {pricing_as_of}" if pricing_as_of else "")
            + ". Not a provider invoice."
        ),
        "baseline_model": baseline_name,
        "cost_pricing_as_of": pricing_as_of,
    }
    outputs: dict[str, Any] = {}
    if cheapest:
        evidence["reallocate"] = {
            "from_model": baseline_name,
            "to_model": cheapest["model_name"],
            "savings_usd": cheapest["savings_usd"],
            "baseline_cost_usd": baseline_cost,
            "candidate_cost_usd": cheapest["cost_usd"],
            "candidate_quote_usd": cheapest["move_quote_usd"],
        }
        outputs["routing_hint"] = "reallocate"
        outputs["to_model"] = cheapest["model_name"]
        decision["commercial_action"] = "reallocate"
        decision["commercial_owner_role"] = "platform"
        decision["commercial_rationale"] = (
            f"Route {baseline_name} → {cheapest['model_name']}; "
            f"quote stays in band, agent floor drops ${cheapest['savings_usd']:.4f}."
        )
        decision["requires_review"] = True
        decision["price_signal"] = "within_policy"
    else:
        decision["price_signal"] = "within_policy"

    decision["rationale"] = (
        f"{decision.get('rationale', '')} {price_sentence(economics, evidence)}"
    ).strip()

    agent_gdr = {
        "record_id": f"gdr_vis_{bakeoff.get('run_id', 'unknown')}",
        "vertical": "agent_runtime",
        "schema_version": "1.0.0",
        "ontology_version": str(profile.get("ontology_version") or "agent_runtime_v1"),
        "evaluated_at": str(evaluated_at),
        "evaluator_id": "capecon_vision_adapter",
        "subject": {
            "workspace_id": WORKSPACE_ID,
            "entity_type": "capability",
            "capability_id": CAPABILITY_ID,
            "capability_version": f"{CAPABILITY_ID}-{bakeoff.get('run_id', 'v1')}",
            "agent_id": AGENT_ID,
        },
        "exceptions": exceptions,
        "economics": economics,
        "decision": decision,
        "evidence": evidence,
        "outputs": outputs,
        "honesty": bakeoff.get("honesty"),
    }
    refuse_mixed_units(agent_gdr, quotes)
    if validate:
        errors = validate_record(agent_gdr, "agent_runtime")
        if errors:
            raise ValueError(f"Invalid vision agent GDR: {errors}")
    tables = bakeoff_to_tables(bakeoff)
    return {
        "agent_gdr": agent_gdr,
        "quote_records": quotes,
        "reallocate": evidence.get("reallocate"),
        "tables": tables,
        "headline_quotes": headline_quote_records(quotes),
    }


def ingest_vision_pack(
    bakeoff_path: str | Path,
    historic_path: str | Path | None = None,
    *,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bakeoff = ingest_vision_bakeoff(bakeoff_path)
    quotes = ingest_vision_historic_jobs(historic_path) if historic_path else []
    return compose_vision_records(bakeoff, quotes, profile=profile)
