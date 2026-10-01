"""Market experiment adapter: Magentic / MarketAgents-shaped exports → Workspace tables.

Does not call Magentic Marketplace or MarketAgents. Hand-authored JSONL only.
Welfare maps to outcome_value_usd when present; CapEcon does not invent a social-welfare function.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from data.adapters.base import (
    AGENT_TXN_COLUMNS,
    OUTCOMES_COLUMNS,
    RUNS_COLUMNS,
    align_frame,
    as_bool,
    as_float,
    load_json_or_jsonl,
    stamp_provenance,
)

ASSIST_TYPES = frozenset(
    {
        "quote_generated",
        "listing_optimized",
        "checkout_completed",
        "negotiation_assisted",
        "none",
    }
)


def ingest_market_export(path: str | Path) -> dict[str, Any]:
    """
    Parse a market experiment JSONL/JSON into runs, outcomes, agent_transactions.

    Each record maps to one transaction + one run + one outcome.
    """
    records = load_json_or_jsonl(path)
    return ingest_market_records(records)


def ingest_market_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    txn_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []
    outcome_rows: list[dict[str, Any]] = []

    for i, rec in enumerate(records):
        tid = str(rec.get("transaction_id") or f"TXN-MKT-{i:04d}")
        run_id = str(rec.get("agent_run_id") or rec.get("run_id") or f"RUN-MKT-{i:04d}")
        cap = str(rec.get("capability_id") or "market_assist")
        cost = as_float(rec.get("agent_inference_cost_usd") or rec.get("run_cost_usd"), 0.0)
        success = as_bool(rec.get("success"), False)
        verified = as_bool(rec.get("verified"), success)
        assist = str(rec.get("agent_assist_type") or "none")
        if assist not in ASSIST_TYPES:
            assist = "none"
        gmv = as_float(rec.get("gmv_usd"), 0.0)
        take = as_float(rec.get("take_rate"), 0.12)
        platform_rev = as_float(rec.get("platform_revenue_usd"), gmv * take)
        occurred = rec.get("occurred_at") or rec.get("started_at") or "2026-01-01T00:00:00Z"
        seller = str(rec.get("seller_id") or f"SELLER-{i:03d}")
        buyer = str(rec.get("buyer_id") or f"BUYER-{i:03d}")
        account = str(rec.get("account_id") or seller)
        value = rec.get("outcome_value_usd")
        if value is None and rec.get("surplus_usd") is not None:
            value = rec.get("surplus_usd")
        value_f = as_float(value, 0.0) if value is not None else None

        initial_bid = as_float(rec.get("initial_bid_usd"), None)
        final_bid = as_float(rec.get("final_bid_usd") or rec.get("agreed_price_usd"), None)
        buyer_val = as_float(rec.get("buyer_valuation_usd"), None)
        seller_cost = as_float(rec.get("seller_cost_usd"), None)
        n_rounds = int(rec.get("negotiation_rounds") or rec.get("proposal_count") or 0)
        order_type = str(rec.get("order_type") or "market")
        spread = as_float(rec.get("bid_ask_spread_usd"), None)

        neg_discount = None
        if initial_bid is not None and final_bid is not None and initial_bid > 0:
            neg_discount = round((initial_bid - final_bid) / initial_bid, 4)

        txn_rows.append(
            {
                "transaction_id": tid,
                "occurred_at": occurred,
                "seller_id": seller,
                "buyer_id": buyer,
                "capability_id": cap,
                "agent_run_id": run_id,
                "gmv_usd": gmv,
                "take_rate": take,
                "platform_revenue_usd": platform_rev,
                "agent_inference_cost_usd": cost,
                "agent_assist_type": assist,
                "verified": verified,
                "verified_by": str(rec.get("verified_by") or "deterministic_stage"),
                "success": success,
                "negotiation_rounds": n_rounds,
                "initial_bid_usd": initial_bid,
                "final_bid_usd": final_bid,
                "buyer_valuation_usd": buyer_val,
                "seller_cost_usd": seller_cost,
                "negotiation_discount": neg_discount,
                "order_type": order_type,
                "bid_ask_spread_usd": spread,
            }
        )
        run_rows.append(
            {
                "run_id": run_id,
                "seat_id": str(rec.get("seat_id") or buyer),
                "capability_id": cap,
                "capability_version_id": str(rec.get("capability_version_id") or f"{cap}:v1"),
                "started_at": occurred,
                "success": success,
                "run_cost_usd": cost,
                "trust_incident": as_bool(rec.get("trust_incident"), False),
            }
        )
        outcome_rows.append(
            {
                "outcome_id": f"OUT-{tid}",
                "account_id": account,
                "end_user_id": buyer,
                "agent_run_id": run_id,
                "outcome_type": str(rec.get("outcome_type") or "market_transaction"),
                "success": success,
                "verified": verified,
                "verified_by": str(rec.get("verified_by") or "deterministic_stage"),
                "occurred_at": occurred,
                "days_since_signup": int(rec.get("days_since_signup") or 0),
                "outcome_value_usd": value_f,
                "list_price_per_outcome_usd": None,
            }
        )

    tables = {
        "agent_transactions": align_frame(txn_rows, AGENT_TXN_COLUMNS),
        "runs": align_frame(run_rows, RUNS_COLUMNS),
        "outcomes": align_frame(outcome_rows, OUTCOMES_COLUMNS),
    }
    return {
        "tables": tables,
        "meta": stamp_provenance("market", claim_type="simulated"),
    }
