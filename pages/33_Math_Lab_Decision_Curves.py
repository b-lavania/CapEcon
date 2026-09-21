"""Math Lab — decision curves / net-benefit analysis."""

from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from analytics.account_risk import enrich_account_records
from analytics.decision_curves import net_benefit_curve, operating_point_from_semantics, optimal_threshold
from analytics.decisions import emit_account_records
from core.workspace import get_workspace_from_session
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.workspace_banner import require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead("Learn", "Math Lab · Decision Curves", "Net-benefit vs threshold — pick your operating point.", cluster="lab")
page_help("math_lab")

ws = require_workspace(st.session_state, page_label="Math Lab")
overlay = st.session_state.get("semantics_overlay")
op = operating_point_from_semantics(overlay)

recs = enrich_account_records(
    emit_account_records(ws, ws.profile, semantics_overlay=overlay),
    ws,
)
y_true = []
y_score = []
for rec in recs:
    acc = rec.get("subject", {}).get("account_id")
    if acc and rec.get("p_churn_30d") is not None:
        seats = ws.seats
        acc_col = "workspace_id" if "workspace_id" in seats.columns else "account_id"
        churned = bool(seats[seats[acc_col] == acc]["is_churned"].any()) if not seats.empty else False
        y_true.append(int(churned))
        y_score.append(rec["p_churn_30d"])

section_kicker("Policy operating point")
st.caption(
    f"From semantics overlay: P(churn_30d) ≥ **{op['p_churn_30d_min']:.0%}** to intervene · "
    f"cost FP=${op['cost_fp']:.0f} · cost FN=${op['cost_fn']:.0f}"
)

if len(y_true) < 3:
    st.info("Generate a workspace with account records in rigorous mode for decision curves.")
else:
    curve = net_benefit_curve(y_true, y_score, cost_fp=op["cost_fp"], cost_fn=op["cost_fn"])
    best = optimal_threshold(curve)
    thresholds = [c["threshold"] for c in curve]
    nb = [c["net_benefit"] for c in curve]
    treat_all = curve[0]["treat_all"] if curve else 0

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=thresholds, y=nb, mode="lines+markers", name="Net benefit"))
    fig.add_hline(y=treat_all, line_dash="dash", annotation_text="Treat all")
    fig.add_hline(y=0, line_dash="dot", annotation_text="Treat none")
    fig.add_vline(x=op["p_churn_30d_min"], line_dash="dash", annotation_text="Semantics threshold")
    if best:
        fig.add_vline(x=best["threshold"], line_color="green", annotation_text="Peak NB")
    fig.update_layout(
        xaxis_title="Threshold P(churn)",
        yaxis_title="Net benefit",
        height=400,
        margin=dict(l=40, r=40, t=40, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    if best:
        st.metric("Peak net benefit", f"{best['net_benefit']:.3f}", help=f"at threshold {best['threshold']:.2f}")

section_kicker("Intuition")
st.markdown(
    """
At your **cost of false rollback** vs **cost of missed churn**, the peak net-benefit threshold
is where intervene/hold wins. Edit `semantics.yaml` posterior thresholds or use Semantics Console
to move the operating point without retraining.
    """
)
