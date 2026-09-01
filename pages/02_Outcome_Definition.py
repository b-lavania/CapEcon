"""Outcome Definition — name verified success, not logins."""

from pathlib import Path

import streamlit as st

from core.workspace import get_workspace_from_session, sync_workspace_to_session
from ontology.outcome_contract import TEMPLATES, VERIFIED_BY, apply_template, default_contract, validate_outcomes
from analytics.value_ledger import sync_outcome_contract_to_workspace
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead(
    "Start",
    "Outcome Definition Kit",
    "Name what verified success is. Login doesn't count.",
)
page_help("outcome_kit")

contract = st.session_state.get("outcome_contract") or default_contract()

section_kicker("1. Agent shape")
template_id = st.selectbox(
    "Template",
    list(TEMPLATES.keys()),
    format_func=lambda k: TEMPLATES[k]["label"],
    index=list(TEMPLATES).index(contract.get("template_id", "quote_ops"))
    if contract.get("template_id") in TEMPLATES
    else 0,
)
st.caption(TEMPLATES[template_id]["notes"])
if template_id != contract.get("template_id"):
    contract = apply_template(template_id)

section_kicker("2. Outcome types")
types_text = st.text_area(
    "One outcome_type per line",
    value="\n".join(contract.get("outcome_types") or []),
)
types = [t.strip() for t in types_text.splitlines() if t.strip()]
contract["outcome_types"] = types
contract["template_id"] = template_id

section_kicker("3. verified_by policy")
policy = dict(contract.get("verified_by_policy") or {})
for t in types:
    policy[t] = st.selectbox(
        f"{t}",
        VERIFIED_BY,
        index=VERIFIED_BY.index(policy.get(t, TEMPLATES[template_id]["preferred_verified_by"]))
        if policy.get(t, TEMPLATES[template_id]["preferred_verified_by"]) in VERIFIED_BY
        else 0,
        key=f"vb_{t}",
    )
contract["verified_by_policy"] = policy
contract["min_verified_share"] = st.slider(
    "Minimum verified share",
    0.0,
    1.0,
    float(contract.get("min_verified_share", 0.4)),
)

section_kicker("4. Task tier (S / M / L)")
tier_options = ["skip", "S", "M", "L"]
current_tier = contract.get("task_tier") or "skip"
tier_pick = st.radio(
    "Scoped task tier",
    tier_options,
    index=tier_options.index(current_tier) if current_tier in tier_options else 0,
    horizontal=True,
)
task_tiers = dict(contract.get("task_tiers") or TEMPLATES[template_id].get("task_tiers") or {})
contract["task_tiers"] = task_tiers
if tier_pick != "skip":
    contract["task_tier"] = tier_pick
    spec = task_tiers.get(tier_pick, {})
    st.caption(f"{spec.get('footprint', '')} · list ${spec.get('list_usd', '—')}")
else:
    contract.pop("task_tier", None)
    st.caption("Skip tier scoping (OK for internal_budget; SKU/marketplace presets should pick a tier).")

section_kicker("5. Default value per outcome_type")
value_map = dict(contract.get("outcome_value_map") or {})
for t in types:
    value_map[t] = st.number_input(
        f"{t} prior value USD (0 = unset)",
        min_value=0.0,
        value=float(value_map.get(t, 0) or 0),
        step=0.01,
        key=f"val_{t}",
    )
contract["outcome_value_map"] = {k: v for k, v in value_map.items() if v > 0}

if st.button("Save contract", type="primary"):
    st.session_state["outcome_contract"] = contract
    ws = get_workspace_from_session(st.session_state)
    if ws is not None:
        sync_outcome_contract_to_workspace(ws, contract)
        sync_workspace_to_session(st.session_state, ws)
    st.success("Contract saved to session and workspace meta.")

ws = get_workspace_from_session(st.session_state)
section_kicker("Readiness gate")
if ws is None:
    st.info("No workspace yet — generate synthetic data or use Data Connect, then return here.")
    st.page_link("pages/01_Data_Connect.py", label="Data Connect")
    st.page_link("pages/00_Agentic_Product_Profile.py", label="Product Profile")
else:
    report = validate_outcomes(getattr(ws, "outcomes", None), contract)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Outcomes", report["n"])
    c2.metric("Verified share", f"{report['verified_share']:.0%}")
    c3.metric("Known types", f"{report['known_types_share']:.0%}")
    c4.metric("Tier", contract.get("task_tier") or "—")
    c5.metric("Ready", "yes" if report["ready"] else "no")
    if report["blockers"]:
        st.warning(" · ".join(report["blockers"]))
        st.caption("If you cannot define outcomes, stop here — the offer is an instrumentation audit, not Version Gate theater.")
    else:
        st.success("Outcome-ready. Open Version Gate.")
        st.page_link("pages/24_Version_Gate.py", label="Version Gate")
    st.json(contract)
