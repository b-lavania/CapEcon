"""Marketplace Radar — agent-assisted GMV economics and workflow decisions."""

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from analytics.decisions import emit_marketplace_records
from analytics.marketplace_economics import (
    agent_gmv_attribution,
    marketplace_margin_shock,
    marketplace_summary_chips,
    seller_margin_table,
)
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
    "Marketplace Radar",
    "Agent-assisted GMV after inference cost — which workflows to throttle.",
    cluster="call",
)
page_help("marketplace_radar", show_card_glossary=True)

ws = require_workspace(st.session_state, page_label="Marketplace Radar")
txn = getattr(ws, "agent_transactions", None)

if txn is None or txn.empty:
    st.info(
        "This surface needs preset **Marketplace (agent-assisted GMV)**. "
        "Current warehouse has no agent transactions."
    )
    st.page_link("pages/00_Agentic_Product_Profile.py", label="Go to Product Profile", icon="⚙️")
    st.stop()

chips = marketplace_summary_chips(ws)
take_rate = chips["take_usd"] / max(chips["gmv_assisted"], 1)
margin_pct = chips["margin_pct"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("GMV (assisted)", f"${chips['gmv_assisted']:,.0f}")
c2.metric("Platform take $", f"${chips['take_usd']:,.0f}")
c3.metric("Inference $", f"${chips['inference_usd']:,.0f}")
c4.metric(
    "Net margin $",
    f"${chips['net_margin_usd']:,.0f}",
    delta=f"{margin_pct:.1%} of GMV",
    delta_color="inverse" if chips["net_margin_usd"] < 0 else "normal",
)
st.caption(
    f"Looks like {take_rate:.0%} take; after inference, platform margin is {margin_pct:.0%}."
)

overlay = st.session_state.get("semantics_overlay")
wfl_records = emit_marketplace_records(
    ws, ws.profile, entity_type="workflow", semantics_overlay=overlay,
)
sel_records = emit_marketplace_records(
    ws, ws.profile, entity_type="seller", semantics_overlay=overlay,
)

tab_wfl, tab_sel, tab_econ = st.tabs(["Workflows to act on", "Seller health", "Economics"])

with tab_wfl:
    if wfl_records:
        labels = [r["subject"].get("capability_id", "?") for r in wfl_records[:12]]
        costs = [r["economics"]["primary_metric_usd"] for r in wfl_records[:12]]
        colors = ["#dc2626" if c > 0 else "#16a34a" for c in costs]
        fig = go.Figure(go.Bar(
            x=costs,
            y=labels,
            orientation="h",
            marker_color=colors,
        ))
        fig.update_layout(
            title="Platform margin at risk by workflow",
            xaxis_title="USD at risk",
            height=max(280, 40 * len(labels)),
            margin=dict(l=40, r=40, t=50, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
    section_kicker("Workflow decisions")
    if not wfl_records:
        st.info("No workflow exceptions for this seed.")
    for i, rec in enumerate(wfl_records[:8]):
        render_decision_card(rec, key_prefix=f"mkt_wfl_{i}", show_override=False, expanded=(i == 0))

with tab_sel:
    sellers = seller_margin_table(ws)
    if not sellers.empty:
        st.dataframe(sellers, use_container_width=True, hide_index=True)
    section_kicker("Seller decisions")
    for i, rec in enumerate(sel_records[:8]):
        render_decision_card(rec, key_prefix=f"mkt_sel_{i}", show_override=False, expanded=(i == 0))

with tab_econ:
    rev = chips["take_usd"]
    inf = chips["inference_usd"]
    net = chips["net_margin_usd"]
    wf = go.Figure(go.Waterfall(
        x=["Take revenue", "Inference cost", "Net margin"],
        y=[rev, -inf, net],
        measure=["relative", "relative", "total"],
    ))
    wf.update_layout(height=360, margin=dict(l=40, r=40, t=40, b=40))
    st.plotly_chart(wf, use_container_width=True)

    attr = agent_gmv_attribution(ws)
    if not attr.empty:
        pivot = attr.pivot_table(
            index="assist_type",
            columns="capability_id",
            values="gmv_usd",
            aggfunc="sum",
            fill_value=0,
        )
        hm = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=list(pivot.columns),
            y=list(pivot.index),
            colorscale="Blues",
        ))
        hm.update_layout(
            title="GMV by assist type × workflow",
            height=360,
            margin=dict(l=40, r=40, t=50, b=40),
        )
        st.plotly_chart(hm, use_container_width=True)

    shock_pct = st.slider("Token price shock %", 0, 100, 0, key="mkt_shock") / 100.0
    shocked = marketplace_margin_shock(ws, shock_pct)
    st.metric(
        f"If tokens +{int(shock_pct * 100)}%, net margin",
        f"${shocked['net_margin_usd']:,.0f}",
        delta=f"${shocked['delta_usd']:+,.0f}",
    )
    st.caption("Synthetic; oracle rates from pricing_oracle.yaml")
