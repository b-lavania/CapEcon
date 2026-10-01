"""Math Lab — packaging sensitivity (synthetic + fitted demand)."""

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from analytics.demand_model import fit_and_cache_demand, get_demand_fit, pypricing_available
from analytics.demand_panel import build_demand_panel, panel_power
from analytics.packaging_sensitivity import (
    breakeven_volume,
    implied_wtp_cap,
    margin_curve,
    synthetic_demand_curve,
)
from analytics.price_block import pricing_mode_for_profile
from analytics.value_ledger import outcome_contract, task_tier_list_usd
from core.workspace import get_workspace_from_session, sync_workspace_to_session
from ui.evidence_chrome import render_claim_badge, render_underpowered_callout
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.workspace_banner import require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead(
    "Lab",
    "Math Lab · Packaging",
    "At what list price does this SKU still clear floor?",
    cluster="lab",
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

panel = build_demand_panel(ws)
power = panel_power(panel)

section_kicker("Demand mode")
if not pypricing_available():
    st.caption("Fitted demand requires `pip install -r requirements-pricing.txt`.")
    demand_mode = "Prior (authored ε)"
else:
    demand_mode = st.radio(
        "Demand curve",
        ["Prior (authored ε)", "Fitted (pypricing)"],
        horizontal=True,
    )

if demand_mode == "Fitted (pypricing)" and pypricing_available():
    if not power["ok"]:
        render_underpowered_callout(" · ".join(power.get("reasons", [])))
    if st.button("Fit demand", type="primary"):
        with st.spinner("Sampling posterior (may take a minute)…"):
            fit_and_cache_demand(ws, panel=panel, draws=300, tune=300, chains=2)
            sync_workspace_to_session(st.session_state, ws)
        st.success("Demand fit cached on workspace.meta['demand_fit'].")

fit = get_demand_fit(ws)
if fit and not fit.get("underpowered"):
    render_claim_badge(fit.get("claim_type", "simulated"))
    sku_fit = (fit.get("skus") or {}).get(str(cap_id), {}) if cap_id != "—" else {}
    if sku_fit:
        c1, c2, c3 = st.columns(3)
        eps = sku_fit.get("elasticity_mean")
        c1.metric("Posterior ε", f"{eps:.2f}" if eps is not None else "—")
        c2.metric("Surplus-opt list", f"${sku_fit.get('surplus_opt_usd') or 0:.2f}")
        c3.metric("Qty mult @ +10%", f"{sku_fit.get('qty_mult_1p10_mean') or '—'}")

section_kicker("Inputs")
c1, c2, c3 = st.columns(3)
floor_usd = c1.number_input("Floor / verified outcome USD", min_value=0.0, value=float(floor_default), step=0.01)
list_default = float(tier_list or econ.get("list_usd") or econ.get("charged_usd") or 0.99) if cap_id != "—" else 0.99
list_usd = c2.number_input("List or take USD", min_value=0.0, value=list_default, step=0.01)
elasticity = c3.slider("Demand elasticity prior", -2.0, 0.0, -0.8, 0.1, disabled=demand_mode.startswith("Fitted"))
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

section_kicker("Margin vs list")
fig_margin = go.Figure()
fig_margin.add_trace(go.Scatter(x=margin_df["list_usd"], y=margin_df["margin_per_outcome"], mode="lines+markers"))
fig_margin.add_vline(x=list_usd, line_dash="dash", line_color="#64748b", annotation_text="current list")
surplus_opt = (fit.get("skus") or {}).get(str(cap_id), {}).get("surplus_opt_usd") if fit and cap_id != "—" else None
if surplus_opt:
    fig_margin.add_vline(x=float(surplus_opt), line_dash="dot", line_color="#16a34a", annotation_text="surplus-opt")
fig_margin.add_hline(y=0, line_color="#dc2626", annotation_text="floor")
fig_margin.update_layout(height=320, margin=dict(l=40, r=40, t=40, b=40))
st.plotly_chart(fig_margin, use_container_width=True)

section_kicker("Quantity vs list")
if demand_mode.startswith("Fitted") and fit and not fit.get("underpowered") and pypricing_available():
    st.caption("Fitted curve uses cached demand_fit; refit with the button above to refresh.")
    conv_df = synthetic_demand_curve(
        0.35,
        list_usd or 1.0,
        float((fit.get("skus") or {}).get(str(cap_id), {}).get("elasticity_mean") or -0.8),
        prices,
    )
    fig_conv = go.Figure()
    fig_conv.add_trace(go.Scatter(x=conv_df["list_usd"], y=conv_df["quantity_pct"] if "quantity_pct" in conv_df else conv_df["conversion_pct"], mode="lines+markers", name="fitted approx"))
else:
    conv_df = synthetic_demand_curve(0.35, list_usd or 1.0, elasticity, prices)
    fig_conv = go.Figure()
    fig_conv.add_trace(go.Scatter(x=conv_df["list_usd"], y=conv_df["conversion_pct"], mode="lines+markers", name="prior"))
fig_conv.add_vline(x=list_usd, line_dash="dash", line_color="#64748b")
fig_conv.update_layout(height=320, yaxis_title="Conversion %", margin=dict(l=40, r=40, t=40, b=40))
st.plotly_chart(fig_conv, use_container_width=True)

st.caption(
    "Fitted mode uses pypricing LogLogDemandModel when installed; prior mode is authored ε. "
    "Not conjoint or market research. claim_type follows workspace data_source."
)
if tier:
    st.caption(
        f"Outcome contract tier **{tier}** · tier list ${tier_list:.2f}"
        if tier_list
        else f"Tier **{tier}** selected."
    )

section_kicker("Pricing archetype comparison")
st.caption(
    "Four archetypes modelled at synthetic volume distribution. "
    "Source: analytics/packaging_sensitivity.py :: archetype_cohort_matrix(). "
    "Claim: simulated (teaching)."
)
from analytics.packaging_sensitivity import archetype_cohort_matrix, archetype_summary

med_outcomes = float(
    ws.profile.get("priors", {}).get(
        "outcomes_per_seat_month",
        max(1.0, (ws.runs["success"].sum() / max(len(ws.seats), 1)) if not ws.runs.empty else 8.0),
    )
)
arpa = float(ws.profile.get("priors", {}).get("seat_arpu_monthly", 49.99))

archetype_cols = st.columns(4)
summary = archetype_summary(floor_usd, arpa, med_outcomes, target_margin)
labels = ["Seat-Based", "Pure Outcome", "Hybrid", "SLA-Backed"]
keys = ["seat_based", "outcome_based", "hybrid", "sla_backed"]
for col, label, key in zip(archetype_cols, labels, keys):
    arch = summary[key]
    col.metric(label, f"${arch['margin_usd']:,.2f}/mo margin", help=arch.get("note", ""))

section_kicker("Cohort gross margin by usage decile")
matrix_df = archetype_cohort_matrix(floor_usd, arpa, med_outcomes)
fig_matrix = go.Figure()
for arch in ["seat_based_margin", "outcome_based_margin", "hybrid_margin", "sla_margin"]:
    fig_matrix.add_trace(
        go.Bar(
            x=matrix_df["decile"],
            y=matrix_df[arch],
            name=arch.replace("_margin", "").replace("_", " ").title(),
        )
    )
fig_matrix.update_layout(
    barmode="group",
    xaxis_title="Usage Decile",
    yaxis_title="Gross Margin USD/mo",
    height=350,
)
st.plotly_chart(fig_matrix, use_container_width=True)
st.caption(
    "Negative seat-based margin at high deciles = power-user subsidy. "
    "Outcome-based pricing restores monotonic margin growth."
)

