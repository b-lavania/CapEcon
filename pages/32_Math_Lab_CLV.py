"""Math Lab — Legacy BG/NBD probabilistic CLV (e-commerce only)."""

from pathlib import Path

import streamlit as st

from analytics.clv_probabilistic import bg_nbd_clv, clv_summary
from core.workspace import get_workspace_from_session
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.workspace_banner import require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead("Learn", "Math Lab · CLV", "BG/NBD teaching CLV on legacy customers/transactions.", cluster="lab")
page_help("math_lab")

ws = require_workspace(st.session_state, page_label="Math Lab CLV")
if ws.customers.empty or ws.transactions.empty:
    st.warning("Legacy customer/transaction tables empty on this profile.")
    st.stop()

section_kicker("Probabilistic CLV")
df = bg_nbd_clv(ws.customers, ws.transactions)
summary = clv_summary(df)
c1, c2, c3 = st.columns(3)
c1.metric("Customers", summary["n"])
c2.metric("Mean CLV", f"${summary['mean_clv']:,.0f}")
c3.metric("Median CLV", f"${summary['median_clv']:,.0f}")
st.dataframe(df.head(20), use_container_width=True, hide_index=True)

st.caption(
    "Agentic account retention uses discrete-time hazard in `analytics/survival.py` — "
    "not BG/NBD. This lab is for legacy e-commerce only."
)
