"""Version Gate — should we ship, hold, or roll back this version?"""

from pathlib import Path

import streamlit as st

from analytics.commercial import commercial_sentence
from analytics.demand_model import demand_caption_for_capability
from analytics.evidence import is_rigorous_mode
from analytics.inference.confidence_sequences import cs_two_proportion
from analytics.price_block import price_sentence
from analytics.value_ledger import value_sentence
from analytics.version_gate import evaluate_version_gate
from ontology.store import upsert_record
from ui.decision_card import render_decision_card
from ui.evidence_chrome import render_claim_badge, render_underpowered_callout
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.workspace_banner import require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead(
    "Decide",
    "Version Gate",
    "Ship, hold, or roll back this capability version.",
)
page_help("version_gate")

ws = require_workspace(st.session_state, page_label="Version Gate")
overlay = st.session_state.get("semantics_overlay")
gate = evaluate_version_gate(ws, semantics_overlay=overlay)
cmp = gate["compare"]

lights = {"red": "RED", "green": "GREEN", "yellow": "YELLOW", "grey": "GREY"}
tl = cmp.get("traffic_light", "yellow")
st.markdown(f"### {lights.get(tl, 'YELLOW')} · `{gate.get('ci_status', 'warn').upper()}` · **{gate.get('recommended_action', 'hold').upper()}**")
render_claim_badge(gate.get("claim_type", "simulated"))
st.caption(" · ".join(r for r in gate.get("reasons") if r))

section_kicker("Pre-deploy eval")
e1, e2, e3 = st.columns(3)
e1.metric("Eval score delta", gate["eval_delta"].get("display", "—"))
e2.metric("CPSO", gate["cpso"].get("display", "—"))
e3.metric("Trust incident rate", gate["trust_incident_rate"].get("display", "—"))
if gate["eval_delta"].get("fail"):
    st.error("Eval regression beyond -10pp — do not ship.")

section_kicker("Price contract")
econ = gate["economics"]
commercial = gate["commercial"]
p1, p2, p3, p4 = st.columns(4)
floor = econ.get("floor_usd")
p1.metric(
    "Floor / verified outcome",
    f"${floor:,.2f}" if floor is not None else "—",
    help="Cost to produce one verified outcome. Absent when nothing verified in window.",
)
cap = econ.get("cap_usd")
cap_label = "Budget cap" if econ.get("pricing_mode") == "internal_budget" else "Policy cap"
p2.metric(cap_label, f"${cap:,.2f}" if cap is not None else "—")
margin = econ.get("margin_usd")
p3.metric("Margin / outcome", f"${margin:,.2f}" if margin is not None else "—")
val = econ.get("value_usd")
n_ver = econ.get("n_verified")
p4.metric(
    "Value / outcome",
    f"${val / n_ver:,.2f}" if val is not None and n_ver else "—",
)
st.caption(price_sentence(econ, {"claim_type": gate.get("claim_type")}))
value_line = value_sentence(econ, {"claim_type": gate.get("claim_type")})
if value_line:
    st.caption(value_line)
cap_id = (gate.get("gdr") or {}).get("subject", {}).get("capability_id")
if not cap_id and gate.get("subject"):
    cap_id = gate["subject"].get("capability_id")
demand_line = demand_caption_for_capability(ws, cap_id)
if demand_line:
    st.caption(demand_line)

if commercial.get("commercial_action"):
    st.warning(f"**{commercial['commercial_action']}** · owner `{commercial.get('commercial_owner_role', 'packaging')}` — {commercial.get('commercial_rationale', '')}")
    st.caption("Commercial actions always require review — churnOS does not change a price book.")
else:
    st.caption(commercial_sentence(commercial))

section_kicker("Canary (SPRT)")
st.caption(f"Previous: `{cmp.get('previous_version', '—')}` · Current: `{cmp.get('current_version', '—')}`")
if cmp.get("rows"):
    st.dataframe(cmp["rows"], use_container_width=True, hide_index=True)
    st.caption(f"JS(outcome mix) = {cmp.get('js_outcome_mix', 0):.3f}")
else:
    st.info("Not enough version history on this seed / ingest.")

sprt = cmp.get("sprt") or {}
with st.expander("Evidence vs peeking (sequential test)", expanded=False):
    if sprt:
        st.write(
            f"SPRT decision: **{sprt.get('decision')}** · LLR {sprt.get('llr')} "
            f"(bounds {sprt.get('boundary_lower')} to {sprt.get('boundary_upper')}) · n={sprt.get('n_total')}"
        )
    if cmp.get("p_value") is not None:
        st.caption(f"Fixed-n two-proportion z-test p-value: {cmp['p_value']:.4f} (peeking inflates false positives)")
    if cmp.get("recommendation") == "hold":
        render_underpowered_callout(cmp.get("n_curr", 0) + cmp.get("n_prev", 0), 60)

cs_expanded = is_rigorous_mode(ws.profile)
with st.expander("Always-valid bounds (confidence sequence)", expanded=cs_expanded):
    cs = cs_two_proportion(
        cmp.get("s_prev", 0), cmp.get("n_prev", 0), cmp.get("s_curr", 0), cmp.get("n_curr", 0),
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("Δ success (pp)", f"{cs.get('delta', 0) * 100:+.1f}")
    m2.metric("CS 95% lo", f"{cs.get('lo', 0) * 100:+.1f}%")
    m3.metric("CS 95% hi", f"{cs.get('hi', 0) * 100:+.1f}%")
    if cs.get("lo", -1) <= 0 <= cs.get("hi", 1):
        st.caption("Do not ship or rollback on this peek — sequence still includes no-difference.")

section_kicker("Emit GDR to Decision Inbox")
gdr = gate["gdr"]
render_decision_card(gdr, key_prefix="vg_preview", show_override=False, expanded=True, workspace=ws)
if st.button("Emit to Inbox + store", type="primary"):
    upsert_record(gdr)
    recs = list(st.session_state.get("growth_records") or [])
    recs = [r for r in recs if r.get("record_id") != gdr["record_id"]]
    recs.insert(0, gdr)
    st.session_state["growth_records"] = recs
    st.success(f"Stored `{gdr['record_id']}` — open Decision Inbox.")
    st.page_link("pages/19_Decision_Inbox.py", label="Decision Inbox")

st.caption("CI: POST /version-gate with run counts (see docs/integrations.md).")
