"""Clinical Radar — OpenMed-shaped clinical runtime economics and review risk."""

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from analytics.clinical_runtime import clinical_summary_chips
from analytics.decisions import emit_clinical_records
from ui.decision_card import render_decision_card
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.workspace_banner import require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead(
    "Decide",
    "Clinical Radar",
    "Residual clinical risk — inference, review labor, and expected harm per SDK capability.",
)
page_help("clinical_radar", show_card_glossary=True)

ws = require_workspace(st.session_state, page_label="Clinical Radar")
cr = getattr(ws, "clinical_runs", None)

if ws.profile.get("ontology_vertical") != "clinical_runtime" or cr is None or cr.empty:
    st.info(
        "This surface needs preset **OpenMed v2.2 — clinical SDK (case study)** "
        "(`clinical_runtime` vertical). Generate a workspace from Product Profile."
    )
    st.page_link("pages/00_Agentic_Product_Profile.py", label="Go to Product Profile", icon="⚙️")
    st.stop()

case = ws.profile.get("case_study") or {}
if case.get("honesty"):
    st.caption(case["honesty"])
if case.get("source_url"):
    st.markdown(f"[OpenMed {case.get('release', '2.2.0')} release notes]({case['source_url']})")

chips = clinical_summary_chips(ws)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Clinical runs", f"{chips['n_runs']:,}")
c2.metric("Mean abstention", f"{chips['mean_abstention']:.0%}")
c3.metric("Review labor $", f"${chips['review_labor_usd']:,.0f}")
c4.metric("Inference $", f"${chips['inference_usd']:,.0f}")

c5, c6, c7 = st.columns(3)
c5.metric("PHI in logs rate", f"{chips['phi_log_rate']:.1%}")
c6.metric("FHIR integrity", f"{chips['fhir_integrity_rate']:.0%}")
c7.metric("Review backlog (hr)", f"{chips['review_backlog_hr']:.1f}")

overlay = st.session_state.get("semantics_overlay")
records = emit_clinical_records(ws, ws.profile, semantics_overlay=overlay)

tab_caps, tab_queue = st.tabs(["Capabilities to act on", "Review queue"])

with tab_caps:
    if records:
        labels = [r["subject"].get("capability_id", "?") for r in records[:12]]
        costs = [r["economics"]["primary_metric_usd"] for r in records[:12]]
        colors = ["#dc2626" if c > 500 else "#d97706" if c > 100 else "#16a34a" for c in costs]
        fig = go.Figure(go.Bar(x=costs, y=labels, orientation="h", marker_color=colors))
        fig.update_layout(
            title="Residual clinical risk by capability",
            xaxis_title="USD",
            height=max(280, 40 * len(labels)),
            margin=dict(l=40, r=40, t=50, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
    section_kicker("Clinical decisions")
    if not records:
        st.info("No clinical exceptions for this seed.")
    for i, rec in enumerate(records[:10]):
        render_decision_card(rec, key_prefix=f"cln_{i}", show_override=False, expanded=(i == 0))

with tab_queue:
    pending = cr[cr["review_required"] & ~cr["review_completed"]]
    st.metric("Pending qualified reviews", len(pending))
    st.metric("Queue P(wait)", f"{chips.get('p_wait', 0):.0%}")
    if not pending.empty:
        agg = (
            pending.groupby("capability_id", as_index=False)
            .agg(
                pending_reviews=("clinical_run_id", "count"),
                mean_wait_hr=("review_wait_hr", "mean"),
                inference_usd=("inference_usd", "sum"),
            )
            .sort_values("pending_reviews", ascending=False)
        )
        st.dataframe(agg, use_container_width=True, hide_index=True)
    st.caption(
        "Synthetic teaching warehouse — review labor is modeled as COGS on every assistive output. "
        "No source clinical text is stored."
    )
