"""Math Lab — distributional drift and change-point detection."""

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from analytics.drift import drift_summary, outcome_distribution_drift
from data.ground_truth import get as get_ground_truth
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.workspace_banner import require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead("Learn", "Math Lab · Drift", "Did the outcome mix shift, and when?", cluster="lab")
page_help("math_drift")

ws = require_workspace(st.session_state, page_label="Math Lab · Drift")
summary = drift_summary(ws)
od = outcome_distribution_drift(ws)

c1, c2, c3 = st.columns(3)
c1.metric("JS (14d vs prior 14d)", f"{od.get('js', 0):.3f}")
c2.metric("KL", f"{od.get('kl', 0):.3f}")
c3.metric("Change-point week", summary.get("change_point_week") or "none")

section_kicker("Outcome mix")
labels = ["success", "fail"]
base = od.get("baseline", [0.5, 0.5])
recent = od.get("recent", [0.5, 0.5])
fig_bar = go.Figure()
fig_bar.add_trace(go.Bar(name="Baseline", x=labels, y=base))
fig_bar.add_trace(go.Bar(name="Recent", x=labels, y=recent))
fig_bar.update_layout(
    barmode="group",
    height=320,
    margin=dict(l=40, r=40, t=40, b=40),
)
st.plotly_chart(fig_bar, use_container_width=True)

section_kicker("Weekly success rate")
weekly = summary.get("weekly")
if weekly is not None and not weekly.empty:
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=weekly["week"],
        y=weekly["success_rate"],
        mode="lines+markers",
        name="Success rate",
    ))
    cp = summary.get("change_point_index")
    if cp is not None:
        cp_week = weekly.iloc[cp]["week"]
        fig_line.add_vline(x=cp_week, line_color="#16a34a", line_dash="dash")
        fig_line.add_annotation(
            x=cp_week,
            y=float(weekly["success_rate"].max()),
            text="CUSUM change-point",
            showarrow=True,
            arrowhead=1,
        )
    fig_line.update_layout(height=360, margin=dict(l=40, r=40, t=40, b=40))
    st.plotly_chart(fig_line, use_container_width=True)

gt = get_ground_truth(ws.seed)
if gt and gt.planted_change_point_week:
    section_kicker("Ground truth recovery")
    detected = summary.get("change_point_week") or "none"
    st.metric("Detected vs planted", f"{detected} vs {gt.planted_change_point_week}")

section_kicker("Intuition")
st.markdown(
    """
Slope drift (steps-to-completion) is already on Radar as `quality_drift`.
This page is **mix shift** + a date — did success/fail proportions move, and when?
    """
)
