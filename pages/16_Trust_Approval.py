"""Trust & Approval — catastrophic events, HITL, post-failure trust."""

from pathlib import Path

import streamlit as st

from analytics.decisions import emit_capability_records
from analytics.metrics import resolve_metric
from ui.decision_card import render_decision_card
from ui.explain import page_help, render_tool_split_caption
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.viz import (
    autonomy_ratio_strip,
    catastrophic_event_timeline,
    human_intervention_timeseries,
    post_failure_trust_bars,
    trust_approval_timeline,
    trust_by_capability,
)
from ui.workspace_banner import empty_records_caption, require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead("The call", "Trust & Approval", "Catastrophic reliability shocks (synthetic).", cluster="call")
page_help("trust", show_card_glossary=True)
render_tool_split_caption("trust")

ws = require_workspace(st.session_state, page_label="Trust & Approval")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Catastrophic rate", resolve_metric("catastrophic_event_rate", ws)["display"])
c2.metric("Human intervention", resolve_metric("human_intervention_rate", ws)["display"])
c3.metric("Post-failure trust Δ", resolve_metric("post_failure_trust_drop", ws)["display"])
c4.metric("Autonomy ratio", resolve_metric("autonomy_ratio", ws)["display"])

section_kicker("Catastrophic event log")
fig_cat = catastrophic_event_timeline(ws)
if fig_cat is not None:
    st.plotly_chart(fig_cat, use_container_width=True)
elif not ws.catastrophic_events.empty:
    st.dataframe(ws.catastrophic_events, use_container_width=True)

section_kicker("Human intervention over time")
fig_hitl = human_intervention_timeseries(ws)
if fig_hitl is not None:
    st.plotly_chart(fig_hitl, use_container_width=True)

section_kicker("Post-failure NPS drop")
fig_nps = post_failure_trust_bars(ws)
if fig_nps is not None:
    st.plotly_chart(fig_nps, use_container_width=True)

section_kicker("Autonomy vs HITL")
fig_auto = autonomy_ratio_strip(ws.runs, ws.approvals)
if fig_auto is not None:
    st.plotly_chart(fig_auto, use_container_width=True)

fig_time = trust_approval_timeline(ws.runs, ws.approvals)
if fig_time is not None:
    section_kicker("Trust & dismiss timeline")
    st.plotly_chart(fig_time, use_container_width=True)

fig_cap = trust_by_capability(ws.runs, ws.capabilities)
if fig_cap is not None:
    section_kicker("Trust by capability")
    st.plotly_chart(fig_cap, use_container_width=True)

records = emit_capability_records(ws, ws.profile, filter_categories={"approval_fatigue", "trust_break", "catastrophic_failure"})
section_kicker("Decision records")
if not records:
    empty_records_caption("trust_break / catastrophic_failure")
for i, rec in enumerate(records[:5]):
    render_decision_card(rec, key_prefix=f"trust_{i}", show_override=False, workspace=ws)
