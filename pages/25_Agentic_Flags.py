"""Agentic feature-flag experiments — CPSO / TTFV / HITL impact (synthetic)."""

from pathlib import Path

import pandas as pd
import streamlit as st

from analytics.flag_segments import flag_segment_table
from analytics.metrics import resolve_metric
from data.challenge_seed import FEATURE_FLAGS
from ui.explain import page_help, render_tool_split_caption
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.viz import feature_flag_impact
from ui.workspace_banner import require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead("Learn", "Agentic Flags", "Treatment vs control on cost, activation, and trust (dummy-seeded).", cluster="after")
page_help("experiments", show_card_glossary=True)
render_tool_split_caption("experiments")
st.info("Dual-layer story: measurement → decision → flywheel. Flags instrument CPSO, TTFV, HITL on synthetic cohorts.", icon="ℹ️")

ws = require_workspace(st.session_state, page_label="Agentic Flags")

c1, c2, c3, c4 = st.columns(4)
c1.metric("CPSO", resolve_metric("cost_per_successful_outcome", ws)["display"])
c2.metric("TTFV", resolve_metric("time_to_first_value", ws)["display"])
c3.metric("HITL rate", resolve_metric("human_intervention_rate", ws)["display"])
c4.metric("Integration depth", resolve_metric("integration_depth_score", ws)["display"])

flag = st.selectbox("Feature flag", FEATURE_FLAGS)
fig = feature_flag_impact(ws, flag)
if fig is not None:
    section_kicker(f"Flag impact: {flag}")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.caption("Regenerate workspace to seed feature-flag assignments.")

section_kicker(f"Segment scan — {flag}")
seg_rows = flag_segment_table(ws, flag)
if seg_rows:
    df = pd.DataFrame(seg_rows)
    display = df.copy()
    display["significant"] = display["fdr_significant"].map({True: "✓ FDR", False: "—"})
    st.dataframe(
        display[["segment", "lift_pp", "p_value", "significant", "n_control", "n_treatment"]],
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Unadjusted winners are segment theatre — only FDR-significant segments are highlighted.")
    for _, row in df.iterrows():
        if not row["fdr_significant"] and row["lift_pp"] > 2:
            st.markdown(
                f'<p style="color:#64748b;">{row["segment"]}: raw lift {row["lift_pp"]:+.1f}pp '
                f"(p={row['p_value']:.3f}) — not significant after BH-FDR</p>",
                unsafe_allow_html=True,
            )
else:
    st.caption("Insufficient segment data for FDR table — regenerate workspace.")

section_kicker("All flags")
for f in FEATURE_FLAGS:
    fig_f = feature_flag_impact(ws, f)
    if fig_f is not None:
        st.plotly_chart(fig_f, use_container_width=True, key=f"flag_{f}")
