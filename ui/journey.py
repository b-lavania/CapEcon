"""Journey chrome: breadcrumbs, related pages, workspace data contract."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from core.workspace import Workspace, get_workspace_from_session


JOURNEY_PAGES: dict[str, dict[str, Any]] = {
    "teacher_map": {
        "phase": "Reference",
        "title": "Map atlas",
        "related": ["profile", "run_economics"],
    },
    "profile": {
        "phase": "Setup",
        "title": "Agentic Product Profile",
        "related": ["radar", "run_economics"],
    },
    "radar": {
        "phase": "The call",
        "title": "Capability Risk Radar",
        "related": ["profile", "activation", "record_inspector"],
    },
    "activation": {
        "phase": "The call",
        "title": "Activation & Habit",
        "tables": ["seats", "runs", "product_events"],
        "related": ["trust", "radar"],
    },
    "trust": {
        "phase": "The call",
        "title": "Trust & Approval Health",
        "tables": ["approvals", "runs"],
        "related": ["activation", "run_economics"],
    },
    "run_economics": {
        "phase": "Price",
        "title": "Run Economics",
        "tables": ["runs", "seats"],
        "related": ["connector", "packaging"],
    },
    "packaging": {
        "phase": "Learn",
        "title": "Lab · Packaging",
        "related": ["run_economics"],
    },
    "connector": {
        "phase": "The call",
        "title": "Connector Blast Radius",
        "tables": ["connector_events", "capabilities"],
        "related": ["run_economics"],
    },
    "experimentation": {
        "phase": "Learn",
        "title": "Experimentation Court",
        "tables": ["experiment_assignments", "experiment_outcomes"],
        "related": ["outcome_flywheel", "record_inspector"],
    },
    "outcome_flywheel": {
        "phase": "After",
        "title": "Outcome Flywheel",
        "related": ["experimentation", "retention"],
    },
    "retention": {
        "phase": "The call",
        "title": "Seat Retention & Churn",
        "tables": ["seats", "retention_marks"],
        "related": ["activation", "unit_economics"],
    },
    "semantics": {
        "phase": "Reference",
        "title": "Semantics Console",
        "related": ["taxonomy", "concepts"],
    },
    "taxonomy": {
        "phase": "Reference",
        "title": "Taxonomy Browser",
        "related": ["semantics", "record_inspector"],
    },
    "record_inspector": {
        "phase": "Reference",
        "title": "Record Inspector",
        "tables": ["growth_records"],
        "related": ["radar", "outcome_flywheel"],
    },
}


def render_journey_header(page_key: str) -> Workspace | None:
    """Render breadcrumb + data contract; return workspace if loaded."""
    spec = JOURNEY_PAGES.get(page_key, {"phase": "CapEcon", "title": page_key, "related": []})
    phase = spec.get("phase", "")
    title = spec.get("title", page_key)

    st.markdown(
        f'<p class="mag-kicker" style="margin-bottom:0.25rem;">{phase} · {title}</p>',
        unsafe_allow_html=True,
    )

    ws = get_workspace_from_session(st.session_state)
    with st.expander("Data contract", expanded=False):
        if ws is None:
            st.caption("No workspace loaded. Configure Agentic Product Profile.")
            return None
        st.caption(f"Seed {ws.seed} · {ws.meta.get('data_version', '—')}")
        for table in spec.get("tables", []):
            df = getattr(ws, table, None)
            if isinstance(df, pd.DataFrame):
                st.write(f"**{table}**: {len(df):,} rows")
        records = st.session_state.get("growth_records", [])
        if records:
            st.write(f"**growth_records**: {len(records)} open")
    return ws


def require_workspace(page_key: str) -> Workspace | None:
    """Journey-page wrapper — delegates to workspace_banner with journey title."""
    from ui.workspace_banner import require_workspace as _require

    spec = JOURNEY_PAGES.get(page_key, {})
    title = spec.get("title", page_key.replace("_", " ").title())
    return _require(st.session_state, page_label=title)
