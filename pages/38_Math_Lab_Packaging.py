"""Math Lab — packaging sensitivity (synthetic demand curves)."""

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from analytics.packaging_sensitivity import (
    breakeven_volume,
    implied_wtp_cap,
    margin_curve,
    synthetic_demand_curve,
)
from analytics.price_block import pricing_mode_for_profile
from analytics.value_ledger import outcome_contract, task_tier_list_usd
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.workspace_banner import require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead(
    "Learn",
    "Math Lab · Packaging",
    "At what list price does this SKU still clear floor?",
)
page_help("math_packaging")

ws = require_workspace(st.session_state, page_label="Math Lab · Packaging")
profile = ws.profile
contract = outcome_contract(ws)
mode = pricing_mode_for_profile(profile)

caps = ws.capabilities
cap_options = caps["capability_id"].astype(str).tolist() if not caps.empty else []
cap_id = st.selectbox("Capability", cap_options or ["—"], disabled=not cap_options)

tier = contract.get("task_tier")
tier_list = task_tier_list_usd(contract) if contract else None
floor_default = 0.43
econ: dict = {}
if cap_id and cap_id != "—":
    from analytics.decisions import price_exceptions
    from ontology.decision_rules import load_rules_for_vertical

    sem_vertical = profile.get("ontology_vertical", "capability_lifecycle")
    semantics = load_rules_for_vertical(sem_vertical)
    econ = price_exceptions([], profile, semantics=semantics, workspace=ws, capability_id=cap_id)
    if econ.get("floor_usd") is not None:
        floor_default = float(econ["floor_usd"])

section_kicker("Inputs")
c1, c2, c3 = st.columns(3)
floor_usd = c1.number_input("Floor / verified outcome USD", min_value=0.0, value=float(floor_default), step=0.01)
list_default = float(tier_list or econ.get("list_usd") or econ.get("charged_usd") or 0.99) if cap_id != "—" else 0.99
list_usd = c2.number_input("List or take USD", min_value=0.0, value=list_default, step=0.01)
elasticity = c3.slider("Demand elasticity prior", -2.0, 0.0, -0.8, 0.1)
target_margin = st.slider("Target margin %", 0, 80, 30) / 100.0

margin_per = list_usd - floor_usd
wtp_cap = implied_wtp_cap(floor_usd, target_margin)
be_vol = breakeven_volume(5000.0, margin_per)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Margin / outcome", f"${margin_per:.2f}")
m2.metric("Implied WTP cap", f"${wtp_cap:.2f}")
m3.metric("Breakeven volume", f"{be_vol:,.0f}" if be_vol else "—")
m4.metric("Pricing mode", mode)

prices = [round(floor_usd * m, 2) for m in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5]]
margin_df = margin_curve(floor_usd, prices)
conv_df = synthetic_demand_curve(0.35, list_usd or 1.0, elasticity, prices)

section_kicker("Margin vs list")
fig_margin = go.Figure()
fig_margin.add_trace(go.Scatter(x=margin_df["list_usd"], y=margin_df["margin_per_outcome"], mode="lines+markers"))
fig_margin.add_vline(x=list_usd, line_dash="dash", line_color="#64748b", annotation_text="current list")
fig_margin.add_hline(y=0, line_color="#dc2626", annotation_text="floor")
fig_margin.update_layout(height=320, margin=dict(l=40, r=40, t=40, b=40))
st.plotly_chart(fig_margin, use_container_width=True)

section_kicker("Synthetic conversion vs list")
fig_conv = go.Figure()
fig_conv.add_trace(go.Scatter(x=conv_df["list_usd"], y=conv_df["conversion_pct"], mode="lines+markers"))
fig_conv.add_vline(x=list_usd, line_dash="dash", line_color="#64748b")
fig_conv.update_layout(height=320, yaxis_title="Conversion %", margin=dict(l=40, r=40, t=40, b=40))
st.plotly_chart(fig_conv, use_container_width=True)

st.caption(
    "Synthetic demand curve for teaching — not conjoint or market research. "
    "claim_type: simulated. Use Radar for cost-of-leaving-live; this page explores list-price sensitivity."
)
if tier:
    st.caption(
        f"Outcome contract tier **{tier}** · tier list ${tier_list:.2f}"
        if tier_list
        else f"Tier **{tier}** selected."
    )
