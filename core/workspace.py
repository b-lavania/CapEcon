"""
Unified agentic workspace: synthetic warehouse + optional legacy tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from data.agentic_generator import DATA_VERSION, SEED, generate_agentic_warehouse
from data.generator import generate_all_data, generate_funnel_events


EMPTY_EVAL_RESULTS = pd.DataFrame(
    columns=["capability_id", "capability_version", "eval_suite_id", "score", "evaluated_at"]
)

EMPTY_ACCOUNTS = pd.DataFrame(columns=["account_id", "tier", "pricing_model", "onboarding_completed", "created_at"])
EMPTY_OUTCOMES = pd.DataFrame(
    columns=[
        "outcome_id", "account_id", "end_user_id", "agent_run_id",
        "outcome_type", "success", "verified", "verified_by", "occurred_at", "days_since_signup",
        "outcome_value_usd", "list_price_per_outcome_usd",
    ]
)
EMPTY_SUBSCRIPTION_EVENTS = pd.DataFrame(
    columns=[
        "event_id", "account_id", "event_type", "occurred_at",
        "old_tier", "new_tier", "old_mrr_usd", "new_mrr_usd",
    ]
)


def build_connector_capability_graph(
    connector_events: pd.DataFrame,
    runs: pd.DataFrame,
    seats: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Derived connector → capability dependency table (Gap 4)."""
    cols = ["connector_id", "capability_id", "call_count", "fail_count", "blast_radius_seats"]
    if connector_events.empty or runs.empty:
        return pd.DataFrame(columns=cols)

    merged = connector_events.merge(
        runs[["run_id", "capability_id", "seat_id"]],
        on="run_id",
        how="inner",
    )
    if merged.empty:
        return pd.DataFrame(columns=cols)

    graph = (
        merged.groupby(["connector_id", "capability_id"], as_index=False)
        .agg(
            call_count=("connector_event_id", "count"),
            fail_count=("success", lambda s: int((~s.astype(bool)).sum())),
            blast_radius_seats=("seat_id", "nunique"),
        )
    )
    return graph


@dataclass
class Workspace:
    """Container for agentic + legacy synthetic tables."""

    seed: int
    profile: dict[str, Any]
    built_at: pd.Timestamp
    # Agentic spine
    workspaces: pd.DataFrame
    seats: pd.DataFrame
    agents: pd.DataFrame
    capabilities: pd.DataFrame
    capability_versions: pd.DataFrame
    runs: pd.DataFrame
    approvals: pd.DataFrame
    connector_events: pd.DataFrame
    product_events: pd.DataFrame
    retention_marks: pd.DataFrame
    experiment_assignments: pd.DataFrame
    experiment_exposures: pd.DataFrame
    experiment_outcomes: pd.DataFrame
    # Methodology measurement layer
    accounts: pd.DataFrame = field(default_factory=lambda: EMPTY_ACCOUNTS.copy())
    end_users: pd.DataFrame = field(default_factory=pd.DataFrame)
    sessions: pd.DataFrame = field(default_factory=pd.DataFrame)
    agent_runs: pd.DataFrame = field(default_factory=pd.DataFrame)
    spans: pd.DataFrame = field(default_factory=pd.DataFrame)
    outcomes: pd.DataFrame = field(default_factory=lambda: EMPTY_OUTCOMES.copy())
    subscriptions: pd.DataFrame = field(default_factory=pd.DataFrame)
    subscription_events: pd.DataFrame = field(default_factory=lambda: EMPTY_SUBSCRIPTION_EVENTS.copy())
    usage_events: pd.DataFrame = field(default_factory=pd.DataFrame)
    # Agentic challenges (dummy-seeded)
    catastrophic_events: pd.DataFrame = field(default_factory=pd.DataFrame)
    routing_decisions: pd.DataFrame = field(default_factory=pd.DataFrame)
    spend_by_step: pd.DataFrame = field(default_factory=pd.DataFrame)
    jevons_elasticity: pd.DataFrame = field(default_factory=pd.DataFrame)
    feature_flag_assignments: pd.DataFrame = field(default_factory=pd.DataFrame)
    retention_features: pd.DataFrame = field(default_factory=pd.DataFrame)
    # Derived / governance
    connector_capability_graph: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    eval_results: pd.DataFrame = field(default_factory=lambda: EMPTY_EVAL_RESULTS.copy())
    # Legacy (for LEGACY nav pages)
    customers: pd.DataFrame = field(default_factory=pd.DataFrame)
    transactions: pd.DataFrame = field(default_factory=pd.DataFrame)
    funnel: pd.DataFrame = field(default_factory=pd.DataFrame)
    marketplace: pd.DataFrame = field(default_factory=pd.DataFrame)
    buyers: pd.DataFrame = field(default_factory=pd.DataFrame)
    marketing: pd.DataFrame = field(default_factory=pd.DataFrame)
    agent_transactions: pd.DataFrame = field(default_factory=pd.DataFrame)
    clinical_runs: pd.DataFrame = field(default_factory=pd.DataFrame)
    default_experiment_id: str = "EXP-CAP-VERSION-001"
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def model_config(self) -> dict[str, Any]:
        return self.profile


def _merge_uploaded(agentic: dict[str, Any], uploaded: dict[str, Any] | None) -> dict[str, Any]:
    """Overlay adapter tables onto a generated warehouse (real ingest on teaching spine)."""
    if not uploaded:
        return agentic
    rng = np.random.default_rng(0)
    seats = agentic.get("seats", pd.DataFrame())
    for key, frame in uploaded.items():
        if frame is None:
            continue
        if isinstance(frame, pd.DataFrame) and frame.empty:
            continue
        if key in ("runs", "agent_runs") and isinstance(frame, pd.DataFrame):
            runs = frame.copy()
            if "run_id" not in runs.columns and "agent_run_id" in runs.columns:
                runs["run_id"] = runs["agent_run_id"]
            spine = agentic.get("runs", pd.DataFrame())
            if "seat_id" not in runs.columns and not seats.empty:
                runs["seat_id"] = [
                    seats["seat_id"].iloc[int(rng.integers(0, len(seats)))] for _ in range(len(runs))
                ]
            if "started_at" not in runs.columns and not spine.empty and "started_at" in spine.columns:
                runs["started_at"] = spine["started_at"].iloc[0]
            if "run_cost_usd" not in runs.columns:
                runs["run_cost_usd"] = 0.0
            if "trust_incident" not in runs.columns:
                runs["trust_incident"] = False
            if not spine.empty:
                agentic["runs"] = pd.concat([spine, runs], ignore_index=True, sort=False)
            else:
                agentic["runs"] = runs
            ar = agentic["runs"].copy()
            ar["agent_run_id"] = ar["run_id"] if "run_id" in ar.columns else ar.index.astype(str)
            agentic["agent_runs"] = ar
            continue
        if key == "spans" and isinstance(frame, pd.DataFrame):
            existing = agentic.get("spans", pd.DataFrame())
            agentic["spans"] = (
                pd.concat([existing, frame], ignore_index=True, sort=False)
                if existing is not None and len(existing)
                else frame
            )
            continue
        agentic[key] = frame
    return agentic


def build_workspace(
    profile: dict[str, Any] | None = None,
    *,
    seed: int = SEED,
    n_sessions: int = 30_000,
    price_runs: bool = True,
    data_source: str = "synthetic",
    otel_path: str | None = None,
    uploaded_tables: dict[str, Any] | None = None,
) -> Workspace:
    """Build agentic warehouse from profile; attach legacy bundle for LEGACY pages."""
    if profile is None:
        from analytics.agentic_profile import get_preset
        profile = get_preset("assistant_heavy")

    profile = dict(profile)
    if profile.get("case_study_id"):
        from data.case_studies import apply_case_study_to_profile, load_case_study

        catalog = load_case_study(profile["case_study_id"])
        profile = apply_case_study_to_profile(profile)
        priors = profile.setdefault("priors", {})
        priors["capability_catalog"] = catalog.get("capabilities", [])

    agentic = generate_agentic_warehouse(profile, seed=seed)
    runs = agentic["runs"]
    if price_runs and not runs.empty:
        from analytics.economics import calculate_run_cost
        runs = calculate_run_cost(runs, profile)
        agentic["runs"] = runs
        if not agentic.get("agent_runs", pd.DataFrame()).empty:
            agentic["agent_runs"] = runs.copy()
            agentic["agent_runs"]["agent_run_id"] = runs["run_id"]

    if data_source == "otel":
        from data.ingestion import ingest_otel_into_agentic

        agentic = ingest_otel_into_agentic(agentic, profile, seed=seed, otel_path=otel_path)

    if data_source in (
        "uploaded",
        "otel",
        "langfuse",
        "vision",
        "market",
        "workflow",
        "rl",
        "macro",
        "abm",
        "finance",
    ) and uploaded_tables:
        agentic = _merge_uploaded(agentic, uploaded_tables)
        runs = agentic["runs"]

    graph = build_connector_capability_graph(
        agentic["connector_events"],
        runs,
    )

    # Seed minimal eval scores for P3 scaffolding (two versions per capability)
    eval_rows = []
    for _, ver in agentic["capability_versions"].iterrows():
        base = 0.78
        # v2 slightly better unless random regression later
        score = base + (0.04 if ver["version"] == "v2" else 0.0)
        eval_rows.append(
            {
                "capability_id": ver["capability_id"],
                "capability_version": ver["capability_version_id"],
                "eval_suite_id": "golden_v1",
                "score": round(score, 3),
                "evaluated_at": ver["shipped_at"],
            }
        )
    eval_results = pd.DataFrame(eval_rows) if eval_rows else EMPTY_EVAL_RESULTS.copy()

    uploaded_txn = None
    if uploaded_tables and isinstance(uploaded_tables.get("agent_transactions"), pd.DataFrame):
        cand = uploaded_tables["agent_transactions"]
        if not cand.empty:
            uploaded_txn = cand

    agent_transactions = pd.DataFrame()
    if uploaded_txn is not None:
        agent_transactions = uploaded_txn.copy()
    elif profile.get("preset_id") == "marketplace_agentic":
        from data.marketplace_agentic_generator import generate_agent_transactions

        agent_transactions = generate_agent_transactions(
            runs, agentic["seats"], agentic["capabilities"], profile, seed=seed,
        )

    clinical_runs = pd.DataFrame()
    if profile.get("ontology_vertical") == "clinical_runtime" and profile.get("case_study_id"):
        from data.case_studies import load_case_study
        from data.clinical_generator import generate_clinical_runs

        catalog = load_case_study(profile["case_study_id"])
        clinical_runs = generate_clinical_runs(
            runs, agentic["capabilities"], catalog, profile, seed=seed,
        )

    legacy = generate_all_data(seed=seed)
    funnel = generate_funnel_events(n_sessions=n_sessions, seed=seed)

    challenge_meta = agentic.get("challenge_meta", {})
    ingest_tables = sorted((uploaded_tables or {}).keys()) if uploaded_tables else []
    meta = {
        "data_version": DATA_VERSION,
        "n_sessions": n_sessions,
        "data_source": data_source,
        "uploaded_tables": ingest_tables,
        **challenge_meta,
    }

    return Workspace(
        seed=int(seed),
        profile=dict(profile),
        built_at=pd.Timestamp.utcnow(),
        workspaces=agentic["workspaces"],
        seats=agentic["seats"],
        agents=agentic["agents"],
        capabilities=agentic["capabilities"],
        capability_versions=agentic["capability_versions"],
        runs=runs,
        approvals=agentic["approvals"],
        connector_events=agentic["connector_events"],
        product_events=agentic["product_events"],
        retention_marks=agentic["retention_marks"],
        experiment_assignments=agentic["experiment_assignments"],
        experiment_exposures=agentic["experiment_exposures"],
        experiment_outcomes=agentic["experiment_outcomes"],
        accounts=agentic.get("accounts", EMPTY_ACCOUNTS.copy()),
        end_users=agentic.get("end_users", pd.DataFrame()),
        sessions=agentic.get("sessions", pd.DataFrame()),
        agent_runs=agentic.get("agent_runs", pd.DataFrame()),
        spans=agentic.get("spans", pd.DataFrame()),
        outcomes=agentic.get("outcomes", EMPTY_OUTCOMES.copy()),
        subscriptions=agentic.get("subscriptions", pd.DataFrame()),
        subscription_events=agentic.get("subscription_events", EMPTY_SUBSCRIPTION_EVENTS.copy()),
        usage_events=agentic.get("usage_events", pd.DataFrame()),
        catastrophic_events=agentic.get("catastrophic_events", pd.DataFrame()),
        routing_decisions=agentic.get("routing_decisions", pd.DataFrame()),
        spend_by_step=agentic.get("spend_by_step", pd.DataFrame()),
        jevons_elasticity=agentic.get("jevons_elasticity", pd.DataFrame()),
        feature_flag_assignments=agentic.get("feature_flag_assignments", pd.DataFrame()),
        retention_features=agentic.get("retention_features", pd.DataFrame()),
        connector_capability_graph=graph,
        eval_results=eval_results,
        customers=legacy["customers"],
        transactions=legacy["transactions"],
        funnel=funnel,
        marketplace=legacy["marketplace"],
        buyers=legacy["buyers"],
        marketing=legacy["marketing"],
        agent_transactions=agent_transactions,
        clinical_runs=clinical_runs,
        meta=meta,
    )


def workspace_to_dict(ws: Workspace) -> dict[str, Any]:
    return {
        "seed": ws.seed,
        "profile": ws.profile,
        "built_at": ws.built_at.isoformat(),
        "workspaces": ws.workspaces,
        "seats": ws.seats,
        "agents": ws.agents,
        "capabilities": ws.capabilities,
        "capability_versions": ws.capability_versions,
        "runs": ws.runs,
        "approvals": ws.approvals,
        "connector_events": ws.connector_events,
        "product_events": ws.product_events,
        "retention_marks": ws.retention_marks,
        "experiment_assignments": ws.experiment_assignments,
        "experiment_exposures": ws.experiment_exposures,
        "experiment_outcomes": ws.experiment_outcomes,
        "accounts": ws.accounts,
        "end_users": ws.end_users,
        "sessions": ws.sessions,
        "agent_runs": ws.agent_runs,
        "spans": ws.spans,
        "outcomes": ws.outcomes,
        "subscriptions": ws.subscriptions,
        "subscription_events": ws.subscription_events,
        "usage_events": ws.usage_events,
        "catastrophic_events": ws.catastrophic_events,
        "routing_decisions": ws.routing_decisions,
        "spend_by_step": ws.spend_by_step,
        "jevons_elasticity": ws.jevons_elasticity,
        "feature_flag_assignments": ws.feature_flag_assignments,
        "retention_features": ws.retention_features,
        "connector_capability_graph": ws.connector_capability_graph,
        "eval_results": ws.eval_results,
        "customers": ws.customers,
        "transactions": ws.transactions,
        "funnel": ws.funnel,
        "marketplace": ws.marketplace,
        "buyers": ws.buyers,
        "marketing": ws.marketing,
        "agent_transactions": ws.agent_transactions,
        "clinical_runs": ws.clinical_runs,
        "default_experiment_id": ws.default_experiment_id,
        "meta": ws.meta,
    }


def workspace_from_dict(data: dict[str, Any]) -> Workspace:
    profile = data.get("profile") or data.get("model_config", {})
    return Workspace(
        seed=int(data["seed"]),
        profile=profile,
        built_at=pd.Timestamp(data.get("built_at", pd.Timestamp.utcnow().isoformat())),
        workspaces=data["workspaces"],
        seats=data["seats"],
        agents=data["agents"],
        capabilities=data["capabilities"],
        capability_versions=data["capability_versions"],
        runs=data["runs"],
        approvals=data["approvals"],
        connector_events=data["connector_events"],
        product_events=data["product_events"],
        retention_marks=data["retention_marks"],
        experiment_assignments=data["experiment_assignments"],
        experiment_exposures=data["experiment_exposures"],
        experiment_outcomes=data["experiment_outcomes"],
        accounts=data.get("accounts", EMPTY_ACCOUNTS.copy()),
        end_users=data.get("end_users", pd.DataFrame()),
        sessions=data.get("sessions", pd.DataFrame()),
        agent_runs=data.get("agent_runs", pd.DataFrame()),
        spans=data.get("spans", pd.DataFrame()),
        outcomes=data.get("outcomes", EMPTY_OUTCOMES.copy()),
        subscriptions=data.get("subscriptions", pd.DataFrame()),
        subscription_events=data.get("subscription_events", EMPTY_SUBSCRIPTION_EVENTS.copy()),
        usage_events=data.get("usage_events", pd.DataFrame()),
        catastrophic_events=data.get("catastrophic_events", pd.DataFrame()),
        routing_decisions=data.get("routing_decisions", pd.DataFrame()),
        spend_by_step=data.get("spend_by_step", pd.DataFrame()),
        jevons_elasticity=data.get("jevons_elasticity", pd.DataFrame()),
        feature_flag_assignments=data.get("feature_flag_assignments", pd.DataFrame()),
        retention_features=data.get("retention_features", pd.DataFrame()),
        connector_capability_graph=data.get(
            "connector_capability_graph",
            build_connector_capability_graph(data["connector_events"], data["runs"]),
        ),
        eval_results=data.get("eval_results", EMPTY_EVAL_RESULTS.copy()),
        customers=data["customers"],
        transactions=data["transactions"],
        funnel=data["funnel"],
        marketplace=data["marketplace"],
        buyers=data["buyers"],
        marketing=data.get("marketing", pd.DataFrame()),
        agent_transactions=data.get("agent_transactions", pd.DataFrame()),
        clinical_runs=data.get("clinical_runs", pd.DataFrame()),
        default_experiment_id=data.get("default_experiment_id", "EXP-CAP-VERSION-001"),
        meta=data.get("meta", {}),
    )


def get_workspace_from_session(session_state: Any) -> Workspace | None:
    raw = session_state.get("workspace")
    if raw is None:
        return None
    if isinstance(raw, Workspace):
        return raw
    return workspace_from_dict(raw)


def sync_workspace_to_session(session_state: Any, ws: Workspace) -> None:
    session_state["workspace"] = workspace_to_dict(ws)
    session_state["workspace_seed"] = ws.seed
    session_state["agentic_profile"] = ws.profile


def ensure_growth_records(session_state: Any, ws: Workspace) -> list[dict]:
    if "growth_records" not in session_state or not session_state["growth_records"]:
        from analytics.decisions import emit_records
        from ontology.store import append_record

        records = emit_records(ws, ws.profile, include_accounts=True)
        session_state["growth_records"] = records
        for r in records[:3]:
            append_record(r)
    return session_state["growth_records"]
