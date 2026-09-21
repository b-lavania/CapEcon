"""Decision Inbox — triage GrowthDecisionRecords, not a dashboard."""

from pathlib import Path

import streamlit as st

from analytics.inbox import TRIAGE_STATES, apply_triage, filter_inbox, owner_roles
from analytics.knapsack import hitl_review_slots, select_interventions_gdr
from core.workspace import ensure_growth_records
from ontology.store import read_records
from ui.decision_card import render_decision_card
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.state_sketches import render_triage_sketch
from ui.workspace_banner import require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead(
    "The call",
    "Decision Inbox",
    "Ranked GrowthDecisionRecords. Route by owner. Review is scarce — knapsack first.",
    cluster="call",
)
page_help("inbox")

roles = ["all"] + owner_roles()
c1, c2, c3, c4 = st.columns(4)
owner = c1.selectbox("Owner role", roles)
status = c2.selectbox("Status", ["all", *TRIAGE_STATES])
verdict = c3.selectbox("Verdict", ["all", "destructive", "uneconomic", "leaking", "needs_review", "healthy", "underpowered"])
review_only = c4.checkbox("requires_review only", value=False)

render_triage_sketch(current=None if status == "all" else status)

ws = require_workspace(st.session_state, page_label="Decision Inbox")
session_recs = ensure_growth_records(st.session_state, ws)
stored = read_records()
by_id = {r["record_id"]: r for r in stored}
for r in session_recs:
    by_id.setdefault(r["record_id"], r)
records = list(by_id.values())

filtered = filter_inbox(
    records,
    owner_role=None if owner == "all" else owner,
    status=None if status == "all" else status,
    verdict=None if verdict == "all" else verdict,
    requires_review=True if review_only else None,
)

slots = hitl_review_slots(ws, ws.profile)
knapsack = select_interventions_gdr(
    [r for r in filtered if r.get("subject", {}).get("entity_type") == "account"] or filtered,
    slots,
)
if knapsack.get("selected"):
    st.info(
        f"HITL capacity this week: **{slots}** slots · knapsack selected "
        f"{len(knapsack['selected'])} · expected savings ~${knapsack.get('total_savings_usd', 0):,.0f}."
    )

section_kicker(f"{len(filtered)} record(s)")
if not filtered:
    st.caption("No records match. Emit from Version Gate or open Radar.")

for i, rec in enumerate(filtered[:12]):
    inbox = rec.get("inbox") or {}
    st.caption(f"{inbox.get('status', 'pending')} · {inbox.get('assignee', '—')} · {inbox.get('owner_role', '')}")
    render_decision_card(rec, key_prefix=f"inbox_{i}", show_override=True, expanded=(i == 0), workspace=ws)
    b1, b2, b3, b4 = st.columns(4)
    if b1.button("In review", key=f"tr_rev_{rec['record_id']}"):
        apply_triage(rec, "in_review")
        st.rerun()
    if b2.button("Resolve", key=f"tr_ok_{rec['record_id']}"):
        apply_triage(rec, "resolved")
        st.rerun()
    if b3.button("Defer", key=f"tr_df_{rec['record_id']}"):
        apply_triage(rec, "deferred")
        st.rerun()
    b4.page_link("pages/20_Outcome_Flywheel.py", label="Flywheel write-back")
