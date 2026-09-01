"""Agentic Product Profile — ontology switch + workspace bootstrap."""

from pathlib import Path

import streamlit as st

from analytics.agentic_profile import PRESETS, get_preset, list_presets
from analytics.decisions import classify, emit_capability_records
from analytics.metrics import resolve_metric
from core.workspace import build_workspace, get_workspace_from_session, sync_workspace_to_session
from analytics.value_ledger import sync_outcome_contract_to_workspace
from ui.explain import page_help, tool_stack_explainer
from ui.instrumentation_checklist import render_instrumentation_checklist
from ui.loop_chrome import render_loop_stepper
from ui.magazine import load_magazine_css, masthead, section_kicker

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead(
    "Configuration",
    "Agentic Product Profile",
    "Choose a product shape. This switches ontology semantics and synthetic warehouse priors.",
)
page_help("profile", show_notice=True)
tool_stack_explainer(expanded=False)
render_loop_stepper(st.session_state, highlight="profile")

st.info(
    "**Required before any chart works:** pick a preset and click **Generate workspace**, "
    "or skip synthetic data and use **Data Connect**. "
    "The first build takes about **30–90 seconds** — wait for the spinner to finish.",
    icon="ℹ️",
)
st.page_link("pages/01_Data_Connect.py", label="Connect real traces / CSVs instead")
st.page_link("pages/02_Outcome_Definition.py", label="Define verified outcomes")

preset_id = st.selectbox(
    "Profile preset",
    list_presets(),
    format_func=lambda k: PRESETS[k]["label"],
    index=list_presets().index(st.session_state.get("agentic_profile", {}).get("preset_id", "assistant_heavy"))
    if st.session_state.get("agentic_profile", {}).get("preset_id") in list_presets()
    else 0,
)

profile = get_preset(preset_id)
st.markdown(f"**{profile['description']}**")
if profile.get("case_study_id"):
    st.caption(
        f"Case study: `{profile['case_study_id']}` — catalog-driven capability names; "
        "not vendor telemetry."
    )
section_kicker("Ontology")
st.write(
    f"Vertical: `{profile['ontology_vertical']}` · Version: `{profile['ontology_version']}` · "
    f"Billing: `{profile.get('billing_model', 'b2b_subscription')}` · Model: `{profile.get('default_model', '—')}`"
)

seed = st.number_input("Workspace seed", min_value=1, max_value=99999, value=int(st.session_state.get("workspace_seed", 42)))
data_source = st.selectbox(
    "Demo data source",
    ["synthetic", "otel"],
    index=0,
    help="Synthetic warehouse, or synthetic + mock OTel spans. Real files: Data Connect.",
)
math_mode = st.selectbox(
    "Math mode",
    ["heuristic", "rigorous"],
    index=0 if profile.get("priors", {}).get("math_mode", "heuristic") == "heuristic" else 1,
    help="Rigorous: calibrated hazard, evidence blocks, survival-priced economics.",
)
profile.setdefault("priors", {})["math_mode"] = math_mode

if st.button("Generate workspace", type="primary"):
    try:
        with st.spinner("Building synthetic warehouse (typically 30–90 seconds)…"):
            ws = build_workspace(
                profile,
                seed=int(seed),
                data_source=data_source,
                n_sessions=5_000,
            )
            contract = st.session_state.get("outcome_contract")
            if contract:
                sync_outcome_contract_to_workspace(ws, contract)
        sync_workspace_to_session(st.session_state, ws)
        st.session_state["growth_records"] = []
        st.session_state.pop("semantics_overlay", None)
        st.success(
            f"Workspace built — {len(ws.seats)} seats, {len(ws.capabilities)} capabilities, "
            f"{len(getattr(ws, 'accounts', ws.workspaces))} accounts."
        )
    except Exception as exc:
        st.error(f"Workspace build failed: {exc}")
        st.exception(exc)

workspace = get_workspace_from_session(st.session_state)
if workspace:
    src = workspace.meta.get("data_source", "synthetic")
    if src in ("synthetic", "otel"):
        st.warning("Using synthetic / mock-OTel demo mode. Data Connect overlays real tables when you have them.")
    render_loop_stepper(st.session_state, highlight="warehouse")
    section_kicker("Warehouse summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Seats", len(workspace.seats))
    c2.metric("Accounts", len(getattr(workspace, "accounts", workspace.workspaces)))
    c3.metric("Outcomes", len(getattr(workspace, "outcomes", [])))
    c4.metric("Runs", len(workspace.runs))
    c5.metric("Capabilities", len(workspace.capabilities))

    section_kicker("Warehouse peek")
    col_a, col_b = st.columns(2)
    with col_a:
        st.caption("Sample capabilities")
        st.dataframe(workspace.capabilities.head(5), use_container_width=True, hide_index=True)
    with col_b:
        st.caption("Run success mix")
        if not workspace.runs.empty and "success" in workspace.runs.columns:
            st.metric("Success rate", f"{workspace.runs['success'].mean():.1%}")

    section_kicker("Classify preview")
    raw = classify(workspace, workspace.profile)
    from collections import Counter
    cat_counts = Counter(e["category"] for e in raw)
    st.caption(f"**{len(raw)}** raw exceptions across capabilities before GDR emit.")
    if cat_counts:
        st.write(dict(cat_counts.most_common(8)))
    preview_recs = emit_capability_records(workspace, workspace.profile)
    st.caption(f"Would emit **{len(preview_recs)}** capability GDRs on Radar.")

    render_instrumentation_checklist(workspace)

    st.caption("Next: **Version Gate** (ship/hold/rollback) or **Radar** from DECIDE.")
