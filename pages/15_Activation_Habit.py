"""Activation & Habit — TTFV, dormant cohorts, activation funnel."""

from pathlib import Path

import streamlit as st

from analytics.decisions import emit_account_records, emit_capability_records
from analytics.metrics import resolve_metric
from ui.decision_card import render_decision_card
from ui.explain import page_help, render_tool_split_caption
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.viz import (
    activation_by_capability,
    activation_funnel_revenue,
    activation_path_mix,
    delegation_ratio_timeseries,
    paying_dormant_table,
    ttfv_payment_histogram,
)
from ui.workspace_banner import empty_records_caption, require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead("The call", "Activation & Habit", "Activation failure disguised as churn (synthetic).", cluster="call")
page_help("activation", show_card_glossary=True)
render_tool_split_caption("activation")
st.caption("Synthetic teaching data")

ws = require_workspace(st.session_state, page_label="Activation & Habit")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("TTFV (payment→verified)", resolve_metric("time_to_first_value", ws)["display"])
c2.metric("Paying-but-dormant", resolve_metric("paying_but_dormant_rate", ws)["display"])
c3.metric("Paid→success 14d", resolve_metric("activation_conversion_paid_success", ws)["display"])
c4.metric("First-win coverage", resolve_metric("first_win_definition_coverage", ws)["display"])
c5.metric("High-LTV path share", resolve_metric("high_ltv_activation_path_share", ws)["display"])

section_kicker("Activation funnel with revenue")
fig_funnel = activation_funnel_revenue(ws)
if fig_funnel is not None:
    st.plotly_chart(fig_funnel, use_container_width=True)

col1, col2 = st.columns(2)
with col1:
    section_kicker("TTFV distribution (from payment)")
    fig_ttfv = ttfv_payment_histogram(ws)
    if fig_ttfv is not None:
        st.plotly_chart(fig_ttfv, use_container_width=True)
with col2:
    section_kicker("Activation path mix")
    fig_path = activation_path_mix(ws)
    if fig_path is not None:
        st.plotly_chart(fig_path, use_container_width=True)

section_kicker("Delegation ratio by cohort")
fig_del = delegation_ratio_timeseries(ws.seats)
if fig_del is not None:
    st.plotly_chart(fig_del, use_container_width=True)

section_kicker("Paying but dormant (14d)")
dormant = paying_dormant_table(ws)
if not dormant.empty:
    st.dataframe(dormant, use_container_width=True)

section_kicker("Capability activation signal")
fig_cap = activation_by_capability(ws.runs, ws.capabilities)
if fig_cap is not None:
    st.plotly_chart(fig_cap, use_container_width=True)

records = emit_capability_records(ws, ws.profile, filter_categories={"activation_leak", "habit_collapse"}) + emit_account_records(ws, ws.profile, filter_categories={"tourist", "product_gap", "activation_failure"})
section_kicker("Decision records")
if not records:
    empty_records_caption("activation_leak / tourist / activation_failure")
for i, rec in enumerate(records[:5]):
    render_decision_card(rec, key_prefix=f"act_{i}", show_override=False, workspace=ws)
