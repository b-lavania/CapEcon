"""Executive Summary — leadership output, not operator chrome."""

from pathlib import Path

import streamlit as st

from analytics.executive import executive_summary, markdown_report, slack_blocks
from core.workspace import ensure_growth_records
from ui.evidence_chrome import render_claim_badge
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.workspace_banner import require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead(
    "After",
    "Executive Summary",
    "The 3–5 decisions that matter this week. Every number carries a claim type.",
    cluster="after",
)
page_help("executive")

ws = require_workspace(st.session_state, page_label="Executive Summary")
records = ensure_growth_records(st.session_state, ws)
summary = executive_summary(ws, records)

st.markdown(f"### {summary['headline']}")
st.caption(summary["claim_disclaimer"])

section_kicker("Pinned metrics")
pins = summary["pins"]
cols = st.columns(5)
for i, pin in enumerate(pins[:4]):
    with cols[i]:
        st.metric(pin.get("label") or pin.get("name"), pin.get("display", "—"))
mean_surplus = summary.get("mean_surplus_usd")
cols[4].metric(
    "Mean surplus / outcome",
    f"${mean_surplus:+.2f}" if mean_surplus is not None else "—",
)

section_kicker("Decisions")
for d in summary["top_decisions"]:
    surplus = d.get("surplus_usd")
    surplus_txt = f" · surplus {surplus:+.2f}/outcome" if surplus is not None else ""
    st.markdown(
        f"**{d.get('action')}** · `{d.get('verdict')}` · "
        f"${d.get('cost_usd') or 0:,.0f}{surplus_txt} · `{d.get('subject', {}).get('entity_type')}` "
        f"`{d.get('subject', {}).get('capability_id') or d.get('subject', {}).get('account_id')}`"
    )
    render_claim_badge(d.get("claim_type") or "associational")
    if d.get("rationale"):
        st.caption(d["rationale"][:400])

section_kicker("Export")
md = markdown_report(summary)
st.download_button("Download markdown", md, file_name="capecon-weekly.md", mime="text/markdown")
st.caption("Print this page from the browser for PDF. Slack blocks below — paste into a webhook payload.")
st.json(slack_blocks(summary))
st.page_link("pages/19_Decision_Inbox.py", label="Triage in Decision Inbox")
st.page_link("pages/40_Integrations.py", label="Wire Slack / PagerDuty")
