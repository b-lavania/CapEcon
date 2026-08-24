"""Connector Blast Radius — integration depth & switching costs."""

from pathlib import Path

import streamlit as st

from analytics.decisions import emit_capability_records
from analytics.metrics import resolve_metric
from ui.decision_card import render_decision_card
from ui.explain import page_help, render_tool_split_caption
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.viz import churn_reason_stacked, connector_blast_radius, connector_fail_rates, integration_depth_chart
from ui.workspace_banner import empty_records_caption, require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead("Decisions", "Connectors", "Integration depth and rip-out risk (synthetic).")
page_help("connector", show_card_glossary=True)
render_tool_split_caption("connector")

ws = require_workspace(st.session_state, page_label="Connectors")

c1, c2, c3 = st.columns(3)
c1.metric("Integration depth (mean)", resolve_metric("integration_depth_score", ws)["display"])
c2.metric("Rebuild/competitor churn", resolve_metric("rebuild_competitor_churn_share", ws)["display"])
c3.metric("Context export rate", resolve_metric("context_export_rate", ws)["display"])

section_kicker("Integration depth by account")
fig_depth = integration_depth_chart(ws)
if fig_depth is not None:
    st.plotly_chart(fig_depth, use_container_width=True)

section_kicker("Churn reasons (switching costs)")
fig_churn = churn_reason_stacked(ws)
if fig_churn is not None:
    st.plotly_chart(fig_churn, use_container_width=True)

if not ws.connector_events.empty:
    section_kicker("Connector failure rates")
    fig_fail = connector_fail_rates(ws.connector_events)
    if fig_fail is not None:
        st.plotly_chart(fig_fail, use_container_width=True)
    graph = getattr(ws, "connector_capability_graph", None)
    fig_blast = connector_blast_radius(ws.connector_events, ws.runs, ws.capabilities, graph=graph if graph is not None and not graph.empty else None)
    if fig_blast is not None:
        section_kicker("Blast radius")
        st.plotly_chart(fig_blast, use_container_width=True)

records = emit_capability_records(ws, ws.profile, filter_categories={"connector_fragility"})
section_kicker("Decision records")
if not records:
    empty_records_caption("connector_fragility")
for i, rec in enumerate(records[:5]):
    render_decision_card(rec, key_prefix=f"conn_{i}", show_override=False, workspace=ws)

st.page_link("pages/27_Subgraph_Health.py", label="Multi-agent handoffs → Subgraph Health")
