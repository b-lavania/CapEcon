"""
Synthetic agentic warehouse generator for CapEcon v2.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd

SEED = 42
DATA_VERSION = "2.1-agentic"

EVENT_TYPES = [
    "capability_expose",
    "run_start",
    "run_success",
    "run_fail",
    "approval_requested",
    "human_decision",
    "connector_error",
    "trust_flag",
    "churn_mark",
    "retention_horizon_hit",
]

CAPABILITY_KINDS = ["agent", "workflow", "tool", "automation", "skill"]
CONNECTORS = ["gmail", "calendar", "hubspot", "slack", "mcp", "rest_api", "computer_use"]
APPROVAL_DECISIONS = ["approve", "edit", "dismiss", "escalate"]


def generate_agentic_warehouse(
    profile: dict[str, Any],
    *,
    seed: int = SEED,
) -> dict[str, pd.DataFrame]:
    """Generate all agentic tables from an AgenticProductProfile dict."""
    priors = profile.get("priors", {})
    rng = np.random.default_rng(seed)

    n_seats = int(priors.get("n_seats", 500))
    n_caps = int(priors.get("n_capabilities", 10))
    activation_rate = float(priors.get("activation_rate", 0.55))
    habit_rate = float(priors.get("weekly_habit_rate", 0.45))
    approval_fatigue = float(priors.get("approval_fatigue_rate", 0.2))
    trust_rate = float(priors.get("trust_incident_rate", 0.04))
    conn_err = float(priors.get("connector_error_rate", 0.1))
    run_cost = float(priors.get("run_cost_per_success", 0.5))
    arpu = float(priors.get("seat_arpu_monthly", 59.0))
    churn_base = float(priors.get("monthly_churn_base", 0.06))

    # --- Planted latents for identifiability lab ---
    from data.ground_truth import GroundTruth, register

    treatment_success_pp = float(priors.get("experiment_treatment_success_pp", 0.04))
    treatment_cost_pct = float(priors.get("experiment_treatment_cost_pct", -0.05))

    start = pd.Timestamp("2024-01-01")
    end = pd.Timestamp("2025-12-31")

    workspaces = pd.DataFrame(
        {
            "workspace_id": [f"WS-{i:04d}" for i in range(max(1, n_seats // 8))],
            "plan": rng.choice(["starter", "pro", "enterprise"], size=max(1, n_seats // 8), p=[0.4, 0.45, 0.15]),
            "created_at": start + pd.to_timedelta(rng.integers(0, 300, size=max(1, n_seats // 8)), unit="D"),
        }
    )

    ws_ids = workspaces["workspace_id"].values
    account_hazard_mult: dict[str, float] = {}
    seat_rows = []
    for i in range(n_seats):
        signup = start + pd.Timedelta(days=int(rng.integers(0, 600)))
        activated = rng.random() < activation_rate
        ws_id = str(rng.choice(ws_ids))
        if ws_id not in account_hazard_mult:
            account_hazard_mult[ws_id] = float(rng.uniform(0.6, 1.8))
        hazard_mult = account_hazard_mult[ws_id]
        churn_prob = min(0.95, churn_base * hazard_mult * (1.4 if not activated else 1.0))
        churned = rng.random() < churn_prob
        churn_date = signup + pd.Timedelta(days=int(rng.integers(30, 400))) if churned else pd.NaT
        seat_rows.append(
            {
                "seat_id": f"SEAT-{i:05d}",
                "workspace_id": ws_id,
                "signup_date": signup,
                "is_activated": activated,
                "is_churned": churned,
                "churn_date": churn_date,
                "seat_arpu_monthly": arpu * rng.uniform(0.85, 1.15),
                "weekly_delegation": rng.random() < habit_rate if activated else False,
                "hazard_multiplier": hazard_mult,
            }
        )
    seats = pd.DataFrame(seat_rows)

    agents = pd.DataFrame(
        {
            "agent_id": [f"AGT-{i:03d}" for i in range(max(3, n_caps // 3))],
            "workspace_id": rng.choice(ws_ids, size=max(3, n_caps // 3)),
            "name": [f"Agent {i}" for i in range(max(3, n_caps // 3))],
        }
    )

    cap_rows = []
    ver_rows = []
    catalog_ids = priors.get("capability_ids")
    if catalog_ids and len(catalog_ids) >= n_caps:
        cap_id_list = [str(c) for c in catalog_ids[:n_caps]]
    else:
        cap_id_list = [f"CAP-{i:03d}" for i in range(n_caps)]

    catalog_meta = {str(c.get("id", "")): c for c in (priors.get("capability_catalog") or []) if c.get("id")}

    for i, cap_id in enumerate(cap_id_list):
        meta = catalog_meta.get(cap_id, {})
        kind = meta.get("capability_kind") or str(rng.choice(CAPABILITY_KINDS))
        harm = rng.random() < 0.15
        dead = rng.random() < 0.1
        cap_rows.append(
            {
                "capability_id": cap_id,
                "agent_id": rng.choice(agents["agent_id"].values),
                "name": meta.get("label") or meta.get("id") or f"{kind.title()} {i}",
                "capability_kind": kind,
                "harm_correlation": harm,
                "is_dead": dead,
            }
        )
        for v in range(2):
            ver_rows.append(
                {
                    "capability_version_id": f"{cap_id}-v{v+1}",
                    "capability_id": cap_id,
                    "version": f"v{v+1}",
                    "shipped_at": start + pd.Timedelta(days=int(rng.integers(60, 500))),
                }
            )
    capabilities = pd.DataFrame(cap_rows)
    capability_versions = pd.DataFrame(ver_rows)

    billing_model = profile.get("billing_model", "b2b_subscription")
    demand_ctx: dict[str, Any] | None = None
    if billing_model == "usage_based" and not capabilities.empty:
        base_lists: dict[str, float] = {}
        for cap_id in capabilities["capability_id"].astype(str):
            h = abs(hash((int(seed), cap_id))) % 1000
            base_lists[cap_id] = round(0.40 + (h / 1000.0) * 1.60, 2)
        capabilities["base_list_usd"] = capabilities["capability_id"].astype(str).map(base_lists)
        cap_ids = list(capabilities["capability_id"].astype(str))
        treated = cap_ids[::2]  # half of SKUs
        shock_day = start + pd.Timedelta(days=int((end - start).days * 0.5))
        shock_week = shock_day.strftime("%G-W%V")
        demand_ctx = {
            "base_list_usd": base_lists,
            "treated_skus": treated,
            "shock_week": shock_week,
            "planted_elasticity": float(priors.get("planted_elasticity", -0.8)),
            "price_shock_mult": 1.15,
        }

    # Version quality: v2 may have planted regression on first cap
    version_success_rates: dict[str, float] = {}
    version_change_points: dict[str, str] = {}
    if not capability_versions.empty:
        first_cap = capability_versions["capability_id"].iloc[0]
        for _, ver in capability_versions.iterrows():
            base_sr = 0.82 if ver["version"] == "v1" else 0.74  # planted step down on v2
            version_success_rates[ver["capability_version_id"]] = base_sr
            if ver["capability_id"] == first_cap and ver["version"] == "v2":
                version_change_points[ver["capability_version_id"]] = str(ver["shipped_at"])

    run_rows = []
    approval_rows = []
    connector_rows = []
    event_rows = []
    run_id = 0
    for _, seat in seats.iterrows():
        n_runs = int(rng.integers(2, 25)) if seat["is_activated"] else int(rng.integers(0, 3))
        for _ in range(n_runs):
            run_id += 1
            rid = f"RUN-{run_id:06d}"
            cap_ver = rng.choice(capability_versions["capability_version_id"].values)
            cap_id = capability_versions.loc[
                capability_versions["capability_version_id"] == cap_ver, "capability_id"
            ].iloc[0]
            ts = seat["signup_date"] + pd.Timedelta(days=int(rng.integers(1, 200)))
            base_sr = version_success_rates.get(cap_ver, 0.78)
            success = rng.random() < base_sr * (1.0 - conn_err * 0.3)
            trust = rng.random() < trust_rate
            cost = run_cost * rng.uniform(0.5, 2.0)
            run_rows.append(
                {
                    "run_id": rid,
                    "seat_id": seat["seat_id"],
                    "capability_id": cap_id,
                    "capability_version_id": cap_ver,
                    "started_at": ts,
                    "success": success,
                    "run_cost_usd": round(cost, 3),
                    "trust_incident": trust,
                }
            )
            # loop_count / steps filled after DataFrame build (bimodal geometric)
            event_rows.append(
                {"seat_id": seat["seat_id"], "event_ts": ts, "event_name": "run_start", "capability_id": cap_id}
            )
            if success:
                event_rows.append(
                    {
                        "seat_id": seat["seat_id"],
                        "event_ts": ts + timedelta(minutes=5),
                        "event_name": "run_success",
                        "capability_id": cap_id,
                    }
                )
            else:
                event_rows.append(
                    {
                        "seat_id": seat["seat_id"],
                        "event_ts": ts + timedelta(minutes=2),
                        "event_name": "run_fail",
                        "capability_id": cap_id,
                    }
                )
            if rng.random() < 0.35:
                dismiss_p = 0.2 if approval_fatigue < 0.25 else 0.35
                probs = [0.5, 0.2, dismiss_p, 0.1]
                probs = [p / sum(probs) for p in probs]
                decision = rng.choice(APPROVAL_DECISIONS, p=probs)
                approval_rows.append(
                    {
                        "approval_id": f"APR-{run_id:06d}",
                        "run_id": rid,
                        "seat_id": seat["seat_id"],
                        "decision": decision,
                        "decided_at": ts + timedelta(minutes=3),
                    }
                )
                event_rows.append(
                    {
                        "seat_id": seat["seat_id"],
                        "event_ts": ts + timedelta(minutes=3),
                        "event_name": "human_decision",
                        "props_json": decision,
                    }
                )
            for _ in range(int(rng.integers(1, 4))):
                conn = rng.choice(CONNECTORS)
                ok = rng.random() > conn_err
                # Downstream write confirmation only meaningful after a successful run + connector ok
                outcome_confirmed = bool(success and ok and rng.random() < 0.8)
                connector_rows.append(
                    {
                        "connector_event_id": f"CONN-{run_id:06d}-{conn}",
                        "run_id": rid,
                        "connector_id": conn,
                        "success": ok,
                        "latency_ms": int(rng.integers(50, 2000)),
                        "outcome_confirmed": outcome_confirmed,
                    }
                )
                if not ok:
                    event_rows.append(
                        {
                            "seat_id": seat["seat_id"],
                            "event_ts": ts,
                            "event_name": "connector_error",
                            "props_json": conn,
                        }
                    )
            if trust:
                event_rows.append(
                    {
                        "seat_id": seat["seat_id"],
                        "event_ts": ts,
                        "event_name": "trust_flag",
                        "capability_id": cap_id,
                    }
                )

    runs = pd.DataFrame(run_rows)
    if not runs.empty:
        # Bimodal loop depth: successes complete quickly; failures thrash
        n = len(runs)
        ok_mask = runs["success"].to_numpy()
        loops = np.empty(n, dtype=int)
        n_ok = int(ok_mask.sum())
        n_fail = n - n_ok
        if n_ok:
            loops[ok_mask] = rng.geometric(0.7, size=n_ok)
        if n_fail:
            loops[~ok_mask] = rng.geometric(0.15, size=n_fail)
        loops = np.clip(loops, 1, 24)
        runs["loop_count"] = loops
        runs["steps_to_completion"] = loops * rng.integers(2, 5, size=n)
        runs["tokens_in"] = (runs["steps_to_completion"] * rng.integers(400, 1200, size=n)).astype(int)
        runs["tokens_out"] = (runs["steps_to_completion"] * rng.integers(80, 400, size=n)).astype(int)
        runs["model_id"] = "gpt-4o"
    else:
        runs["loop_count"] = pd.Series(dtype=int)
        runs["steps_to_completion"] = pd.Series(dtype=int)
        runs["tokens_in"] = pd.Series(dtype=int)
        runs["tokens_out"] = pd.Series(dtype=int)
        runs["model_id"] = pd.Series(dtype=str)

    approvals = pd.DataFrame(approval_rows) if approval_rows else pd.DataFrame(
        columns=["approval_id", "run_id", "seat_id", "decision", "decided_at"]
    )
    connector_events = (
        pd.DataFrame(connector_rows)
        if connector_rows
        else pd.DataFrame(
            columns=[
                "connector_event_id",
                "run_id",
                "connector_id",
                "success",
                "latency_ms",
                "outcome_confirmed",
            ]
        )
    )

    retention_rows = []
    for _, seat in seats.iterrows():
        for horizon in (14, 28):
            retained = not seat["is_churned"] or (
                pd.notna(seat["churn_date"])
                and (seat["churn_date"] - seat["signup_date"]).days > horizon
            )
            retention_rows.append(
                {
                    "seat_id": seat["seat_id"],
                    "horizon_days": horizon,
                    "retained": retained,
                }
            )
        if seat["is_churned"]:
            event_rows.append(
                {
                    "seat_id": seat["seat_id"],
                    "event_ts": seat["churn_date"],
                    "event_name": "churn_mark",
                }
            )
    retention_marks = pd.DataFrame(retention_rows)
    product_events = pd.DataFrame(event_rows)

    experiment_id = "EXP-CAP-VERSION-001"
    cap_vers = capability_versions["capability_version_id"].unique()
    assign_rows = []
    for _, seat in seats.iterrows():
        variant = rng.choice(["control", "variant"])
        assign_rows.append(
            {
                "seat_id": seat["seat_id"],
                "experiment_id": experiment_id,
                "capability_version_id": rng.choice(cap_vers),
                "variant": variant,
                "assigned_at": seat["signup_date"] + timedelta(days=int(rng.integers(0, 14))),
            }
        )
    experiment_assignments = pd.DataFrame(assign_rows)

    # Apply planted treatment effect to variant runs
    if not runs.empty and treatment_success_pp != 0:
        variant_seats = set(
            experiment_assignments.loc[experiment_assignments["variant"] == "variant", "seat_id"]
        )
        mask = runs["seat_id"].isin(variant_seats)
        for idx in runs.index[mask]:
            if rng.random() < treatment_success_pp:
                runs.at[idx, "success"] = True
            elif rng.random() < abs(treatment_success_pp):
                runs.at[idx, "success"] = False
        if treatment_cost_pct != 0 and "run_cost_usd" in runs.columns:
            runs.loc[mask, "run_cost_usd"] = (
                runs.loc[mask, "run_cost_usd"] * (1.0 + treatment_cost_pct)
            ).round(3)

    exp_out = []
    for variant in ("control", "variant"):
        sub = experiment_assignments[experiment_assignments["variant"] == variant]
        seat_ids = set(sub["seat_id"])
        sub_runs = runs[runs["seat_id"].isin(seat_ids)]
        successes = sub_runs[sub_runs["success"]]
        exposed = max(len(seat_ids), 1)
        converted = min(len(successes), exposed - 1)  # ensure room for beta prior
        exp_out.append(
            {
                "experiment_id": experiment_id,
                "variant": variant,
                "exposed_seats": exposed,
                "successful_runs": converted,
                "success_rate_pct": round(converted / max(len(sub_runs), 1) * 100, 2),
                # legacy columns for funnel-based tooling
                "visitors": exposed,
                "conversions": converted,
            }
        )
    experiment_outcomes = pd.DataFrame(exp_out)
    experiment_exposures = experiment_assignments.groupby("seat_id", as_index=False).first()

    methodology = _build_methodology_tables(
        workspaces, seats, runs, connector_events, priors, rng, start,
        billing_model=billing_model,
        demand_ctx=demand_ctx,
    )

    from data.challenge_seed import enrich_challenge_data

    payload = {
        "workspaces": workspaces,
        "seats": seats,
        "agents": agents,
        "capabilities": capabilities,
        "capability_versions": capability_versions,
        "runs": runs,
        "approvals": approvals,
        "connector_events": connector_events,
        "product_events": product_events,
        "retention_marks": retention_marks,
        "experiment_assignments": experiment_assignments,
        "experiment_exposures": experiment_exposures,
        "experiment_outcomes": experiment_outcomes,
        **methodology,
    }
    enriched = enrich_challenge_data(payload, profile, seed=seed)

    pop_churn = float(seats["is_churned"].mean()) if not seats.empty else churn_base
    churn_reason_codes = {}
    if not seats.empty and "churn_reason" in seats.columns:
        churned = seats[seats["is_churned"] == True]  # noqa: E712
        churn_reason_codes = dict(churned.groupby("account_id")["churn_reason"].first()) if "account_id" in churned.columns else {}
    outcomes_df = enriched.get("outcomes", pd.DataFrame())
    planted_value_mean = 0.0
    if outcomes_df is not None and not outcomes_df.empty and "outcome_value_usd" in outcomes_df.columns:
        planted_value_mean = float(pd.to_numeric(outcomes_df["outcome_value_usd"], errors="coerce").fillna(0).mean())
    planted_wtp = float(profile.get("priors", {}).get("policy_cpso_cap", 0.5) or 0.5)
    gt_elasticity = float(demand_ctx["planted_elasticity"]) if demand_ctx else -0.8
    gt_shock = demand_ctx["shock_week"] if demand_ctx else None
    gt_treated = list(demand_ctx["treated_skus"]) if demand_ctx else []
    gt_base_lists = dict(demand_ctx["base_list_usd"]) if demand_ctx else {}
    register(
        GroundTruth(
            seed=int(seed),
            workspace_id="ALL",
            monthly_churn_base=churn_base,
            population_churn_rate=pop_churn,
            account_hazard_multipliers=account_hazard_mult,
            version_success_rates=version_success_rates,
            version_change_points=version_change_points,
            experiment_id=experiment_id,
            experiment_treatment_effect_success=treatment_success_pp,
            experiment_treatment_effect_cost_pct=treatment_cost_pct,
            churn_reason_codes=churn_reason_codes,
            planted_outcome_value_mean=planted_value_mean,
            planted_task_tier_list_usd={"S": 0.49, "M": 0.99, "L": 2.49},
            planted_price_change_week=gt_shock if demand_ctx else None,
            planted_conversion_at_price=0.42,
            planted_wtp_cap_usd=planted_wtp,
            planted_elasticity=gt_elasticity,
            planted_shock_week=gt_shock,
            planted_treated_skus=gt_treated,
            planted_base_list_usd=gt_base_lists,
        )
    )
    enriched["ground_truth_seed"] = int(seed)
    return enriched


def _list_at_week(
    cap_id: str,
    week: str,
    demand_ctx: dict[str, Any] | None,
) -> float | None:
    if not demand_ctx:
        return None
    base = float(demand_ctx["base_list_usd"].get(str(cap_id), 0.99))
    if str(cap_id) in demand_ctx.get("treated_skus", []) and week >= demand_ctx.get("shock_week", "9999"):
        return round(base * float(demand_ctx.get("price_shock_mult", 1.15)), 4)
    return round(base, 4)


def _apply_demand_elasticity_thin(
    outcomes: pd.DataFrame,
    runs: pd.DataFrame,
    demand_ctx: dict[str, Any] | None,
    rng: np.random.Generator,
) -> pd.DataFrame:
    if outcomes.empty or demand_ctx is None or runs.empty:
        return outcomes
    run_cap = runs.set_index("run_id")["capability_id"].astype(str).to_dict()
    eps = float(demand_ctx.get("planted_elasticity", -0.8))
    shock = demand_ctx.get("shock_week", "")
    treated = set(demand_ctx.get("treated_skus", []))
    mult = float(demand_ctx.get("price_shock_mult", 1.15))
    keep_rows = []
    for _, row in outcomes.iterrows():
        cap_id = str(run_cap.get(row.get("agent_run_id"), ""))
        if not row.get("verified") or not row.get("success"):
            keep_rows.append(row)
            continue
        occurred = pd.to_datetime(row["occurred_at"])
        week = occurred.strftime("%G-W%V")
        if cap_id in treated and week >= shock:
            keep_p = mult ** eps
            if rng.random() <= keep_p:
                keep_rows.append(row)
        else:
            keep_rows.append(row)
    return pd.DataFrame(keep_rows) if keep_rows else outcomes.iloc[0:0].copy()


def _build_methodology_tables(
    workspaces: pd.DataFrame,
    seats: pd.DataFrame,
    runs: pd.DataFrame,
    connector_events: pd.DataFrame,
    priors: dict[str, Any],
    rng: np.random.Generator,
    start: pd.Timestamp,
    billing_model: str = "b2b_subscription",
    demand_ctx: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    """Methodology-layer entities (§3–4) with thin legacy adapters (seats/runs)."""
    billing = billing_model
    accounts = pd.DataFrame(
        {
            "account_id": workspaces["workspace_id"],
            "tier": workspaces["plan"],
            "pricing_model": billing,
            "onboarding_completed": rng.random(len(workspaces)) > 0.2,
            "created_at": workspaces["created_at"],
        }
    )

    end_users = seats.rename(columns={"seat_id": "end_user_id"}).copy()
    end_users["account_id"] = end_users["workspace_id"]
    seat_to_workspace = seats.set_index("seat_id")["workspace_id"].to_dict()
    seat_to_signup = pd.to_datetime(seats.set_index("seat_id")["signup_date"]).to_dict()
    end_user_to_account = end_users.set_index("end_user_id")["account_id"].to_dict()
    verified_run_ids: set[str] = set()
    if not connector_events.empty and "outcome_confirmed" in connector_events.columns:
        verified_run_ids = set(
            connector_events.groupby("run_id")["outcome_confirmed"].any().loc[lambda s: s].index.astype(str)
        )

    session_rows: list[dict[str, Any]] = []
    span_rows: list[dict[str, Any]] = []
    outcome_rows: list[dict[str, Any]] = []
    usage_rows: list[dict[str, Any]] = []

    if not runs.empty:
        run_df = runs.copy()
        run_df["started_at"] = pd.to_datetime(run_df["started_at"])
        run_df["session_day"] = run_df["started_at"].dt.floor("D")
        run_cap = run_df.set_index("run_id")["capability_id"].astype(str).to_dict()
        for (seat_id, day), grp in run_df.groupby(["seat_id", "session_day"]):
            session_id = f"SES-{seat_id}-{day.strftime('%Y%m%d')}"
            session_rows.append(
                {
                    "session_id": session_id,
                    "end_user_id": seat_id,
                    "account_id": seat_to_workspace.get(seat_id, "WS-0000"),
                    "started_at": grp["started_at"].min(),
                    "ended_at": grp["started_at"].max(),
                    "run_count": len(grp),
                }
            )
            for _, run in grp.iterrows():
                loops = int(run.get("loop_count", 1) or 1)
                for li in range(loops):
                    span_rows.append(
                        {
                            "span_id": f"SPN-{run['run_id']}-{li}",
                            "agent_run_id": run["run_id"],
                            "session_id": session_id,
                            "loop_iteration": li + 1,
                            "tokens_in": int(run.get("tokens_in", 0) / max(loops, 1)),
                            "tokens_out": int(run.get("tokens_out", 0) / max(loops, 1)),
                            "success": bool(run["success"] if li == loops - 1 else True),
                        }
                    )
                usage_rows.append(
                    {
                        "usage_event_id": f"USE-{run['run_id']}",
                        "account_id": end_user_to_account.get(seat_id, "WS-0000"),
                        "agent_run_id": run["run_id"],
                        "tokens_in": int(run.get("tokens_in", 0)),
                        "tokens_out": int(run.get("tokens_out", 0)),
                        "cost_usd": float(run.get("run_cost_usd", 0)),
                        "recorded_at": run["started_at"],
                    }
                )
                if run["success"]:
                    verified = str(run["run_id"]) in verified_run_ids
                    verified_by = "connector_write" if verified else None
                    signup = seat_to_signup.get(seat_id)
                    days_since = int((run["started_at"] - signup).days) if signup is not None else 0
                    outcome_value = None
                    if verified and billing == "usage_based":
                        list_anchor = float(priors.get("policy_cpso_cap", 0.99) or 0.99)
                        if rng.random() < 0.6:
                            outcome_value = round(float(rng.lognormal(np.log(max(list_anchor * 1.2, 0.01)), 0.25)), 2)
                    row = {
                        "outcome_id": f"OUT-{run['run_id']}",
                        "account_id": end_user_to_account.get(seat_id, "WS-0000"),
                        "end_user_id": seat_id,
                        "agent_run_id": run["run_id"],
                        "outcome_type": "task_completion",
                        "success": True,
                        "verified": verified,
                        "verified_by": verified_by,
                        "occurred_at": run["started_at"],
                        "days_since_signup": days_since,
                    }
                    cap_id = str(run_cap.get(run["run_id"], ""))
                    week = pd.to_datetime(run["started_at"]).strftime("%G-W%V")
                    list_p = _list_at_week(cap_id, week, demand_ctx)
                    if list_p is not None:
                        row["list_price_per_outcome_usd"] = list_p
                    elif billing == "usage_based":
                        row["list_price_per_outcome_usd"] = round(
                            float(priors.get("policy_cpso_cap", 0.99) or 0.99), 2
                        )
                    if outcome_value is not None:
                        row["outcome_value_usd"] = outcome_value
                    outcome_rows.append(row)

    sessions = pd.DataFrame(session_rows) if session_rows else pd.DataFrame(
        columns=["session_id", "end_user_id", "account_id", "started_at", "ended_at", "run_count"]
    )
    agent_runs = runs.copy()
    if not agent_runs.empty:
        agent_runs["agent_run_id"] = agent_runs["run_id"]
    spans = pd.DataFrame(span_rows) if span_rows else pd.DataFrame(
        columns=["span_id", "agent_run_id", "session_id", "loop_iteration", "tokens_in", "tokens_out", "success"]
    )
    outcomes = pd.DataFrame(outcome_rows) if outcome_rows else pd.DataFrame(
        columns=[
            "outcome_id", "account_id", "end_user_id", "agent_run_id",
            "outcome_type", "success", "verified", "verified_by", "occurred_at", "days_since_signup",
            "outcome_value_usd", "list_price_per_outcome_usd",
        ]
    )
    if not outcomes.empty and demand_ctx is not None:
        outcomes = _apply_demand_elasticity_thin(outcomes, runs, demand_ctx, rng)

    sub_rows = []
    event_rows: list[dict[str, Any]] = []
    list_per_outcome = float(priors.get("policy_cpso_cap", 0.99) or 0.99)
    for _, acc in accounts.iterrows():
        seat_sub = seats[seats["workspace_id"] == acc["account_id"]]
        mrr = float(seat_sub["seat_arpu_monthly"].sum()) if len(seat_sub) else float(priors.get("seat_arpu_monthly", 59))
        sub = {
            "subscription_id": f"SUB-{acc['account_id']}",
            "account_id": acc["account_id"],
            "mrr_usd": round(mrr, 2),
            "started_at": acc["created_at"],
            "tier": acc["tier"],
            "list_price_per_outcome_usd": None,
            "price_changed_at": None,
            "previous_mrr_usd": None,
        }
        if billing == "usage_based":
            sub["list_price_per_outcome_usd"] = round(list_per_outcome, 2)
            if rng.random() < 0.25:
                change_at = start + pd.Timedelta(days=int(rng.integers(14, 60)))
                sub["price_changed_at"] = change_at
                sub["previous_mrr_usd"] = round(mrr * 0.85, 2)
                sub["mrr_usd"] = round(mrr * 1.12, 2)
                event_rows.append(
                    {
                        "event_id": f"EVT-{acc['account_id']}-price",
                        "account_id": acc["account_id"],
                        "event_type": "price_increase",
                        "occurred_at": change_at,
                        "old_tier": acc["tier"],
                        "new_tier": acc["tier"],
                        "old_mrr_usd": sub["previous_mrr_usd"],
                        "new_mrr_usd": sub["mrr_usd"],
                    }
                )
        sub_rows.append(sub)
    subscriptions = pd.DataFrame(sub_rows)
    subscription_events = pd.DataFrame(event_rows) if event_rows else pd.DataFrame(
        columns=[
            "event_id", "account_id", "event_type", "occurred_at",
            "old_tier", "new_tier", "old_mrr_usd", "new_mrr_usd",
        ]
    )
    usage_events = pd.DataFrame(usage_rows) if usage_rows else pd.DataFrame(
        columns=["usage_event_id", "account_id", "agent_run_id", "tokens_in", "tokens_out", "cost_usd", "recorded_at"]
    )

    return {
        "accounts": accounts,
        "end_users": end_users,
        "sessions": sessions,
        "agent_runs": agent_runs,
        "spans": spans,
        "outcomes": outcomes,
        "subscriptions": subscriptions,
        "subscription_events": subscription_events,
        "usage_events": usage_events,
    }
