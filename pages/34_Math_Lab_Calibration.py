"""Math Lab — hazard calibration and permutation attributions."""

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from analytics.survival import (
    calibration_metrics,
    fit_discrete_hazard_mle,
    hazard_permutation_importance,
    reliability_bins,
)
from core.workspace import get_workspace_from_session
from data.ground_truth import get as get_ground_truth
from ui.evidence_chrome import render_evidence_block
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.workspace_banner import require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead("Learn", "Math Lab · Calibration", "Reliability diagram + hazard feature attributions.", cluster="lab")
page_help("math_lab")

ws = require_workspace(st.session_state, page_label="Math Lab")
fit = fit_discrete_hazard_mle(ws)

section_kicker("Fitted hazard model")
if not fit.get("fitted"):
    st.info("Not enough churn events for MLE — try a larger workspace or different seed.")
else:
    cal = fit.get("calibration", {})
    c1, c2, c3 = st.columns(3)
    c1.metric("Accounts", fit.get("n_accounts", 0))
    c2.metric("Brier score", f"{cal.get('brier', 0):.3f}")
    c3.metric("ECE", f"{cal.get('ece', 0):.3f}")

    bins = fit.get("reliability") or []
    if bins:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[b["predicted_mean"] for b in bins],
            y=[b["observed_rate"] for b in bins],
            mode="markers+lines",
            name="Observed",
        ))
        fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line_dash="dash", name="Perfect"))
        fig.update_layout(
            xaxis_title="Predicted P(churn)",
            yaxis_title="Observed rate",
            height=360,
            margin=dict(l=40, r=40, t=40, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.json({k: v for k, v in fit.items() if k != "_clf"})

gt = get_ground_truth(ws.seed)
if gt and gt.account_hazard_multipliers:
    section_kicker("Ground truth recovery")
    st.caption("Higher planted hazard multipliers should rank higher under fitted scores.")
    multipliers = gt.account_hazard_multipliers
    ranked = sorted(multipliers.items(), key=lambda x: -x[1])[:5]
    st.write({acc: f"{m:.2f}×" for acc, m in ranked})

section_kicker("Permutation attributions (account)")
seats = ws.seats
acc_col = "workspace_id" if "workspace_id" in seats.columns else "account_id"
if not seats.empty:
    acc_id = str(seats[acc_col].iloc[0])
    attrs = hazard_permutation_importance(ws, acc_id, fit)
    if attrs:
        fig2 = go.Figure(go.Bar(
            x=[a["importance"] for a in attrs],
            y=[a["feature"] for a in attrs],
            orientation="h",
        ))
        fig2.update_layout(height=280, margin=dict(l=40, r=40, t=20, b=40))
        st.plotly_chart(fig2, use_container_width=True)
        for a in attrs[:3]:
            st.caption(f"**{a['feature']}** — importance {a['importance']:.3f} ({a['direction']})")

section_kicker("Intuition")
st.markdown(
    """
**Calibration** asks whether a 20% risk score means ~20% of similar accounts churn.
**Attributions** show which features moved this account's score — not causal proof, but an audit trail
for the Decision Card in rigorous mode.
    """
)
