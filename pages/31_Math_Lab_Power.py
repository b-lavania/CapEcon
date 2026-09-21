"""Math Lab — Power for agents, not ads."""

from pathlib import Path

import streamlit as st

from analytics.experimentation import agentic_sample_size
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.evidence_chrome import render_underpowered_callout

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead("Learn", "Math Lab · Power", "Cluster-aware sample size — web CVR vs agent success.", cluster="lab")
page_help("math_lab")

section_kicker("Web CRO pain (why ~300k?)")
web = agentic_sample_size(0.02, 0.001, unit="visitor")
st.write(web["message"])
st.caption(f"Naive n/arm: **{web['sample_size_per_arm_naive']:,}**")

section_kicker("Agent run success")
baseline = st.slider("Baseline success rate", 0.5, 0.95, 0.75, 0.01)
mde_pp = st.slider("MDE (absolute pp)", 0.01, 0.15, 0.05, 0.01)
agent = agentic_sample_size(baseline, mde_pp, unit="run")
st.write(agent["message"])
st.caption(f"Naive n/arm: **{agent['sample_size_per_arm_naive']:,}**")

section_kicker("Cluster trap (ICC)")
icc = st.slider("ICC (intra-cluster correlation)", 0.0, 0.5, 0.1, 0.01)
runs_per = st.slider("Runs per seat", 1, 100, 50)
clustered = agentic_sample_size(baseline, mde_pp, unit="account", icc=icc, runs_per_unit=runs_per)
st.write(
    f"Design effect **{clustered['design_effect']}** → "
    f"**{clustered['sample_size_per_arm_clustered']:,}** accounts/arm "
    f"(was {clustered['sample_size_per_arm_naive']:,} naive)"
)
if clustered["sample_size_per_arm_clustered"] > clustered["sample_size_per_arm_naive"] * 1.5:
    st.warning("ICC inflates required clusters — analyzing runs as i.i.d. visitors overstates power.")

section_kicker("Underpowered example")
render_underpowered_callout(42, clustered["sample_size_per_arm_clustered"])
