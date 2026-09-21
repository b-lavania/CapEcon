"""Taxonomy browser — live counts + churn taxonomy report."""

from pathlib import Path

import streamlit as st

from analytics.churn_taxonomy_report import churn_taxonomy_summary, exception_counts_from_records
from analytics.decisions import emit_account_records, emit_capability_records
from core.workspace import get_workspace_from_session
from ontology.exception_taxonomy import ACTIONS, CATEGORIES, VERDICTS
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.workspace_banner import require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead("Ontology", "Taxonomy Browser", "Exception categories with live workspace counts.")
page_help("taxonomy")

ws = require_workspace(st.session_state, page_label="Taxonomy Browser")
overlay = st.session_state.get("semantics_overlay")
records = emit_capability_records(ws, ws.profile, semantics_overlay=overlay) + emit_account_records(
    ws, ws.profile, semantics_overlay=overlay,
)
counts = exception_counts_from_records(records)

section_kicker("Live exception counts (current workspace)")
if counts:
    st.table([{"category": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])])
    st.caption("Filter Radar (The call) by these categories.")
else:
    st.caption("No exceptions on this seed.")

section_kicker("Churn taxonomy — intervention effectiveness (stub)")
churn_df = churn_taxonomy_summary(ws, records)
st.dataframe(churn_df, use_container_width=True, hide_index=True)
st.caption("Saved = flagged accounts with outcome write-back and no churn. Synthetic demo data.")

from analytics.evidence import is_rigorous_mode
from analytics.survival import cause_specific_incidence
import plotly.express as px

if is_rigorous_mode(ws.profile):
    section_kicker("Competing risks (cause-specific incidence)")
    cs = cause_specific_incidence(ws)
    if not cs.empty:
        fig = px.bar(cs, x="cause", y="hazard_rate", color="cause", title="Cause-specific hazard vs taxonomy")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(cs, hide_index=True, use_container_width=True)

section_kicker("Exception categories")
for key, meta in CATEGORIES.items():
    n = counts.get(key, 0)
    with st.expander(f"{key} ({n} live)"):
        st.write(f"**Owner:** {meta['owner_role']}")
        st.write(f"**Severity:** {meta['default_severity']}")
        st.write(meta["playbook_hint"])

section_kicker("Verdicts & actions")
st.write(", ".join(VERDICTS))
st.write(", ".join(ACTIONS))
