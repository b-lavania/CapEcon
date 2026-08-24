"""
churnOS — Decision-grade analytics for agentic software systems.
Navigation: START → DECIDE → LEARN (+ Reference / Legacy expanders).
"""

import streamlit as st
from pathlib import Path

from analytics.account_risk import enrich_account_records
from analytics.decisions import emit_account_records, emit_capability_records
from analytics.evidence import apply_evsi_review_gate, is_rigorous_mode
from analytics.knapsack import hitl_review_slots, select_interventions_gdr
from analytics.pareto import rank_capability_records
from core.workspace import get_workspace_from_session
from ui.decision_card import render_decision_card
from ui.explain import how_it_works, measurement_honesty, page_help, tool_stack_explainer
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.weekly_report import render_meta_chips, render_weekly_account_report
from ui.workspace_banner import (
    empty_workspace_panel,
    render_sidebar_brand_and_status,
    render_sidebar_secondary_nav,
)

st.set_page_config(page_title="churnOS", layout="wide", initial_sidebar_state="expanded")

css_path = Path(__file__).parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


def capability_risk_radar():
    load_magazine_css()
    masthead(
        "Capability Risk Radar",
        "What to ship, throttle, or kill",
        "Ranked GrowthDecisionRecords priced by cost of leaving live.",
    )

    ws = get_workspace_from_session(st.session_state)
    if ws is None:
        empty_workspace_panel(page_label="Radar")
        page_help("radar", show_card_glossary=False)
        how_it_works(expanded=False)
        tool_stack_explainer(expanded=False)
        return

    how_it_works(expanded=False)

    overlay = st.session_state.get("semantics_overlay")
    acc_records = enrich_account_records(
        emit_account_records(ws, ws.profile, semantics_overlay=overlay),
        ws,
    )
    cap_records = emit_capability_records(ws, ws.profile, semantics_overlay=overlay)
    rank_mode = ws.profile.get("priors", {}).get("radar_rank_mode", "cost")
    cap_records = rank_capability_records(cap_records, ws, mode=rank_mode)
    acc_records = [apply_evsi_review_gate(r, ws.profile) for r in acc_records]
    cap_records = [apply_evsi_review_gate(r, ws.profile) for r in cap_records]
    st.session_state["growth_records"] = acc_records + cap_records

    render_meta_chips(ws, n_acc=len(acc_records), n_cap=len(cap_records))

    if is_rigorous_mode(ws.profile):
        slots = hitl_review_slots(ws, ws.profile)
        knapsack = select_interventions_gdr(acc_records, slots)
        if knapsack.get("selected"):
            st.info(
                f"**This week under HITL capacity ({slots} slots):** "
                f"review {len(knapsack['selected'])} account(s) — "
                f"expected savings ~${knapsack['total_savings_usd']:,.0f}."
            )

    delegation_alerts = sum(
        1 for r in acc_records
        if any(e.get("category") in ("habit_collapse", "tourist", "efficiency") for e in r.get("exceptions", []))
    )
    if delegation_alerts:
        st.warning(f"{delegation_alerts} account(s) tripped delegation / habit signals this week.")

    def _apply_override(rec, action, reason):
        from analytics.decisions import apply_override
        from ontology.store import append_record

        records = st.session_state.get("growth_records") or []
        idx = next(
            (i for i, r in enumerate(records) if r["record_id"] == rec["record_id"]),
            None,
        )
        updated = apply_override(rec, action, reason)
        if idx is not None:
            records[idx] = updated
            st.session_state["growth_records"] = records
        append_record(updated)
        st.session_state["pending_flywheel_ids"] = st.session_state.get("pending_flywheel_ids", []) + [rec["record_id"]]

    tab_accounts, tab_caps = st.tabs(["Weekly account health", "Capabilities to act on"])

    with tab_accounts:
        render_weekly_account_report(ws, acc_records)
        with st.expander("Health charts & reference", expanded=False):
            from analytics.metrics import resolve_metric
            from ui.viz import agentic_health_composite, portfolio_tornado

            page_help("radar", show_card_glossary=True)
            measurement_honesty()
            health_fig = agentic_health_composite(ws)
            if health_fig is not None:
                st.plotly_chart(health_fig, use_container_width=True)
            h1, h2, h3, h4 = st.columns(4)
            h1.metric("Health score", resolve_metric("agentic_health_score", ws)["display"])
            h2.metric("CPSO", resolve_metric("cost_per_successful_outcome", ws)["display"])
            h3.metric("TTFV", resolve_metric("time_to_first_value", ws)["display"])
            h4.metric("Unattributed spend", resolve_metric("unattributed_spend_percentage", ws)["display"])
            fig = portfolio_tornado(acc_records)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)

        section_kicker("Act on accounts")
        for i, rec in enumerate(acc_records[:8]):
            render_decision_card(
                rec,
                key_prefix=f"radar_acc_{i}",
                on_override=_apply_override,
                expanded=(i == 0),
                workspace=ws,
            )

    with tab_caps:
        fig = None
        from ui.viz import portfolio_tornado
        fig = portfolio_tornado(cap_records)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Top {min(8, len(cap_records))} capability decisions.")
        rank_mode = ws.profile.get("priors", {}).get("radar_rank_mode", "cost")
        if rank_mode == "pareto":
            st.caption("Pareto mode — dominated capabilities ranked lower.")
        if not cap_records:
            st.info("No capability GDRs for this seed.")
        for i, rec in enumerate(cap_records[:8]):
            if rec.get("pareto_caption"):
                st.caption(rec["pareto_caption"])
            render_decision_card(
                rec,
                key_prefix=f"radar_cap_{i}",
                on_override=_apply_override,
                expanded=(i == 0),
                workspace=ws,
            )


_REFERENCE_PAGES = [
    st.Page("pages/7_Concepts.py", title="Concepts", url_path="concepts", visibility="hidden"),
    st.Page("pages/6_README.py", title="Architecture", url_path="architecture", visibility="hidden"),
    st.Page("pages/21_Semantics_Console.py", title="Semantics", url_path="semantics", visibility="hidden"),
    st.Page("pages/22_Taxonomy_Browser.py", title="Taxonomy", url_path="taxonomy", visibility="hidden"),
    st.Page("pages/23_Record_Inspector.py", title="Record Inspector", url_path="records", visibility="hidden"),
]

_LEGACY_PAGES = [
    st.Page("pages/99_Legacy_Index.py", title="Legacy (reference)", url_path="legacy", visibility="hidden"),
    st.Page("pages/0_Business_Model.py", title="Business Model", url_path="legacy_business_model", visibility="hidden"),
    st.Page("pages/1_Retention_Churn.py", title="Retention & Churn", url_path="legacy_retention", visibility="hidden"),
    st.Page("pages/2_Unit_Economics.py", title="Unit Economics", url_path="legacy_unit_economics", visibility="hidden"),
    st.Page("pages/11_Product_Lifecycle.py", title="Lifecycle & NSM", url_path="legacy_lifecycle", visibility="hidden"),
    st.Page("pages/4_Marketplace.py", title="Pricing Analytics", url_path="legacy_pricing", visibility="hidden"),
    st.Page("pages/5_Marketplace_Analytics.py", title="Seller Analytics", url_path="legacy_sellers", visibility="hidden"),
    st.Page("pages/8_ECommerce_Analytics.py", title="RFM & Inventory", url_path="legacy_rfm", visibility="hidden"),
    st.Page("pages/9_Marketplace_Liquidity.py", title="Marketplace Liquidity", url_path="legacy_liquidity", visibility="hidden"),
    st.Page("pages/10_Attribution_MMM.py", title="Attribution & MMM", url_path="legacy_mmm", visibility="hidden"),
    st.Page("pages/12_CRO_Program.py", title="CRO Program", url_path="legacy_cro", visibility="hidden"),
    st.Page("pages/13_Revenue_Leakage.py", title="Revenue Leakage", url_path="legacy_leakage", visibility="hidden"),
    st.Page("pages/14_Conversion_Forecast.py", title="Conversion Forecast", url_path="legacy_forecast", visibility="hidden"),
]

nav_structure = {
    "START": [
        st.Page(
            "pages/00_Agentic_Product_Profile.py",
            title="Product Profile",
            url_path="profile",
            default=True,
        ),
        st.Page("pages/01_Data_Connect.py", title="Data Connect", url_path="data_connect"),
        st.Page("pages/02_Outcome_Definition.py", title="Outcome Definition", url_path="outcomes"),
    ],
    "DECIDE": [
        st.Page("pages/24_Version_Gate.py", title="Version Gate", url_path="version_gate"),
        st.Page("pages/19_Decision_Inbox.py", title="Decision Inbox", url_path="inbox"),
        st.Page(capability_risk_radar, title="Radar", url_path="radar"),
        st.Page("pages/27_Subgraph_Health.py", title="Subgraph Health", url_path="subgraph"),
        st.Page("pages/15_Activation_Habit.py", title="Activation & Habit", url_path="activation"),
        st.Page("pages/16_Trust_Approval.py", title="Trust & Approval", url_path="trust"),
        st.Page("pages/17_Run_Economics.py", title="Run Economics", url_path="run_economics"),
        st.Page("pages/18_Connector_Blast_Radius.py", title="Connectors", url_path="connectors"),
        st.Page("pages/35_Marketplace_Radar.py", title="Marketplace Radar", url_path="marketplace_radar"),
        st.Page("pages/41_Clinical_Radar.py", title="Clinical Radar", url_path="clinical_radar"),
        st.Page("pages/26_Agent_Version_Compare.py", title="Version Compare", url_path="version_compare"),
    ],
    "LEARN": [
        st.Page("pages/37_Executive_Summary.py", title="Executive Summary", url_path="executive"),
        st.Page("pages/3_Conversion.py", title="Experiments", url_path="experiments"),
        st.Page("pages/25_Agentic_Flags.py", title="Agentic Flags", url_path="agentic_flags"),
        st.Page("pages/20_Outcome_Flywheel.py", title="Outcome Flywheel", url_path="flywheel"),
        st.Page("pages/30_Math_Lab_Binomial.py", title="Lab · Binomial", url_path="math_binomial"),
        st.Page("pages/31_Math_Lab_Power.py", title="Lab · Power", url_path="math_power"),
        st.Page("pages/32_Math_Lab_CLV.py", title="Lab · CLV", url_path="math_clv"),
        st.Page("pages/33_Math_Lab_Decision_Curves.py", title="Lab · Decision Curves", url_path="math_decision_curves"),
        st.Page("pages/34_Math_Lab_Calibration.py", title="Lab · Calibration", url_path="math_calibration"),
        st.Page("pages/36_Math_Lab_Drift.py", title="Lab · Drift", url_path="math_drift"),
        *_REFERENCE_PAGES,
        *_LEGACY_PAGES,
    ],
    "CONFIG": [
        st.Page("pages/40_Integrations.py", title="Integrations", url_path="integrations"),
    ],
}

pg = st.navigation(nav_structure, expanded=True)
render_sidebar_brand_and_status(st.session_state)
render_sidebar_secondary_nav()
pg.run()
