"""Subgraph / multi-agent health — handoffs, coordination cost, blast radius."""

from pathlib import Path

import streamlit as st

from analytics.metrics import resolve_metric
from analytics.orchestration import (
    blast_radius_top,
    build_handoff_table,
    emit_subgraph_records,
)
from ontology.store import upsert_record
from ui.decision_card import render_decision_card
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.workspace_banner import require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead(
    "The call",
    "Subgraph Health",
    "Handoffs, coordination cost, connector blast radius.",
    cluster="call",
)
page_help("subgraph")

ws = require_workspace(st.session_state, page_label="Subgraph Health")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Handoff success", resolve_metric("handoff_success_rate", ws)["display"])
c2.metric("Coordination cost", resolve_metric("coordination_cost_ratio", ws)["display"])
c3.metric("Retry amplification", resolve_metric("retry_amplification_factor", ws)["display"])
c4.metric("Orphaned subtasks", resolve_metric("orphaned_subtask_rate", ws)["display"])
st.metric("Trust-boundary violations", resolve_metric("trust_boundary_violation_rate", ws)["display"])

section_kicker("Handoff table (A→B by seat sequence)")
table = build_handoff_table(ws)
if table.empty:
    st.info("Not enough sequential capability changes on this warehouse to form handoffs.")
else:
    st.dataframe(table.sort_values("success_rate"), use_container_width=True, hide_index=True)
    worst = table.sort_values("success_rate").iloc[0]
    st.caption(
        f"Weakest handoff: **{worst['from_capability_id']} → {worst['to_capability_id']}** "
        f"({worst['success_rate']:.0%} success, n={int(worst['n'])})."
    )

section_kicker("Connector blast radius")
blast = blast_radius_top(ws, 8)
if blast is not None and not blast.empty:
    st.dataframe(blast, use_container_width=True, hide_index=True)
st.page_link("pages/18_Connector_Blast_Radius.py", label="Full connector page")

section_kicker("Subgraph GDRs")
recs = emit_subgraph_records(ws, semantics_overlay=st.session_state.get("semantics_overlay"))
if not recs:
    st.success("No orchestration exceptions above threshold — agent mesh healthy on this seed.")
for i, rec in enumerate(recs[:6]):
    render_decision_card(rec, key_prefix=f"sg_{i}", show_override=False, expanded=(i == 0), workspace=ws)
if recs and st.button("Emit subgraph records to Inbox"):
    bag = list(st.session_state.get("growth_records") or [])
    for rec in recs:
        upsert_record(rec)
        bag.insert(0, rec)
    st.session_state["growth_records"] = bag
    st.success(f"Emitted {len(recs)} workflow GDRs.")
    st.page_link("pages/19_Decision_Inbox.py", label="Decision Inbox")
