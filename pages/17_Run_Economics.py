"""Run Economics — agentic challenge cost & visibility findings."""

from pathlib import Path

import streamlit as st

from analytics.decisions import emit_account_records, emit_capability_records
from analytics.economics import seat_margins
from analytics.metrics import resolve_metric
from ui.decision_card import render_decision_card
from ui.explain import page_help, render_tool_split_caption
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.viz import (
    cm_nrr_teaching_chart,
    context_util_alert,
    context_util_histogram,
    cost_attribution_heatmap,
    cost_waterfall_sample,
    cpso_trend_line,
    jevons_elasticity_chart,
    loop_histogram,
    power_user_margin_table,
    retry_by_capability,
    run_cost_by_capability,
    run_gantt_sample,
)
from ui.workspace_banner import empty_records_caption, require_workspace
from ui.state_sketches import render_two_axis_sketch

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead("Price", "Run Economics", "Floor, CPSO, WTP, and margin leakage — can we charge this?", cluster="price")
page_help("run_economics", show_card_glossary=True)
render_two_axis_sketch()
render_tool_split_caption("run_economics")
st.caption("Synthetic teaching data — see docs/honesty.md")
st.page_link("pages/38_Math_Lab_Packaging.py", label="Lab · Packaging (demand curve) →")

ws = require_workspace(st.session_state, page_label="Run Economics")
_src = ws.meta.get("data_source")
if _src in ("rl", "macro", "abm", "finance"):
    st.caption(
        f"Figures include an ingested `{_src}` sim export (`claim_type: simulated`), not billing telemetry."
    )
if (
    _src == "finance"
    and "pnl_usd" in ws.outcomes.columns
    and ws.outcomes["pnl_usd"].notna().any()
):
    _pnl = float(ws.outcomes["pnl_usd"].sum())
    st.caption(f"Finance export blotter PnL sum: ${_pnl:,.2f} (caption only; not a VaR).")

billing_options = ["b2b_subscription", "usage_based"]
current = ws.profile.get("billing_model", "b2b_subscription")
billing = st.radio("Billing model simulation", billing_options, index=billing_options.index(current) if current in billing_options else 0, horizontal=True)
view_profile = dict(ws.profile)
view_profile["billing_model"] = billing

margins = seat_margins(ws.runs, ws.seats, view_profile)
neg_share = margins["margin_negative"].mean() * 100 if len(margins) else 0

_show_reward = _src == "rl" and "reward" in ws.runs.columns
_cols = st.columns(6 if _show_reward else 5)
_cols[0].metric("CPSO", resolve_metric("cost_per_successful_outcome", ws)["display"])
_cols[1].metric("Power-user margin", resolve_metric("power_user_margin_leakage", ws)["display"])
_cols[2].metric("Retry amplification", resolve_metric("retry_amplification_factor", ws)["display"])
_cols[3].metric("Unattributed spend", resolve_metric("unattributed_spend_percentage", ws)["display"])
_cols[4].metric("Static routing age", resolve_metric("static_decision_age_median", ws)["display"])
if _show_reward:
    _cols[5].metric("Reward per $", resolve_metric("reward_per_dollar", ws)["display"])

section_kicker("Token production & agency economics")
from analytics.token_production import cascade_opportunity, token_bloat_flags
from analytics.agency_contract import compute_agency_surplus

_tok_cols = st.columns(3)
cascade = cascade_opportunity(ws)
agency = compute_agency_surplus(ws)
bloat_df = token_bloat_flags(ws)
n_bloat = int(bloat_df["flag"].sum()) if not bloat_df.empty else 0

_tok_cols[0].metric(
    "Token bloat capabilities",
    str(n_bloat),
    help="Capabilities where token cost saturates without marginal outcome lift.",
)
_tok_cols[1].metric(
    "Cascade savings estimate",
    f"${cascade['savings_usd']:,.2f}",
    help="Estimated monthly savings from down-routing saturated capabilities (simulated).",
)
delta_str = f"${abs(agency['agency_surplus_usd']):.3f} {'deficit' if agency['agency_deficit'] else 'surplus'}"
_tok_cols[2].metric(
    "Agency surplus / deficit",
    delta_str,
    delta=f"vs ${agency['human_baseline_usd']:.2f} baseline",
    delta_color="inverse" if agency["agency_deficit"] else "normal",
)

section_kicker("CPSO trend")
fig_cpso = cpso_trend_line(ws)
if fig_cpso is not None:
    st.plotly_chart(fig_cpso, use_container_width=True)

ctx_alert = context_util_alert(ws)
if ctx_alert["alert"]:
    st.warning(
        f"Context alert: {ctx_alert['high_share_pct']:.0f}% of runs exceed 80% context utilization "
        f"(mean {ctx_alert['mean_pct']:.0f}%)."
    )

section_kicker("Cost attribution heatmap")
fig_hm = cost_attribution_heatmap(ws)
if fig_hm is not None:
    st.plotly_chart(fig_hm, use_container_width=True)

section_kicker("Jevons elasticity")
fig_j = jevons_elasticity_chart(ws)
if fig_j is not None:
    st.plotly_chart(fig_j, use_container_width=True)

c6, c7 = st.columns(2)
with c6:
    section_kicker("Context window utilization")
    fig_ctx = context_util_histogram(ws)
    if fig_ctx is not None:
        st.plotly_chart(fig_ctx, use_container_width=True)
with c7:
    section_kicker("Retry amplification by capability")
    fig_retry = retry_by_capability(ws.runs, ws.capabilities)
    if fig_retry is not None:
        st.plotly_chart(fig_retry, use_container_width=True)

section_kicker("Agent run Gantt (sample)")
fig_gantt = run_gantt_sample(ws)
if fig_gantt is not None:
    st.plotly_chart(fig_gantt, use_container_width=True)

section_kicker("CM-NRR teaching chart")
fig_cm = cm_nrr_teaching_chart(getattr(ws, "subscriptions", __import__("pandas").DataFrame()), getattr(ws, "usage_events", __import__("pandas").DataFrame()), ws.runs)
if fig_cm is not None:
    st.plotly_chart(fig_cm, use_container_width=True)

from analytics.evidence import is_rigorous_mode
from analytics.stochastic_economics import bootstrap_cm_nrr, conformal_cpso_band
from analytics.queueing import hitl_queue_from_workspace
from ui.evidence_chrome import render_posterior_ribbon

if is_rigorous_mode(view_profile):
    section_kicker("Stochastic margin honesty")
    stoch = bootstrap_cm_nrr(ws)
    cpso_band = conformal_cpso_band(ws)
    s1, s2, s3 = st.columns(3)
    s1.metric("CM-NRR (mean)", f"{stoch['cm_nrr_mean']:.1%}")
    s2.metric("P(CM-NRR < 100%)", f"{stoch['p_cm_nrr_below_1']:.0%}")
    s3.metric("CPSO 90% band", f"${cpso_band['cpso_ci90'][0]:.2f}–${cpso_band['cpso_ci90'][1]:.2f}")
    st.caption(
        f"Looks like {stoch['cm_nrr_mean']:.0%} NRR; "
        f"{stoch['p_cm_nrr_below_1']:.0%} chance CM-NRR < 100%."
    )
    render_posterior_ribbon(stoch["cm_nrr_mean"], stoch["cm_nrr_ci90"], label="CM-NRR")

    section_kicker("HITL queueing (Erlang-C)")
    q = hitl_queue_from_workspace(ws, view_profile)
    q1, q2, q3 = st.columns(3)
    q1.metric("P(wait)", f"{q['p_wait']:.0%}")
    q2.metric("Expected wait (hr)", f"{q['expected_wait_hr']:.1f}")
    q3.metric("Utilization", f"{q['utilization']:.0%}")
    st.caption(
        f"At current HITL load (λ={q['arrival_rate']}/hr, c={q['reviewers']} reviewers), "
        f"P(wait>SLA {q['sla_hours']}hr) ≈ {q['p_wait_exceeds_sla']:.0%}."
    )

    from analytics.knapsack import hitl_review_slots, select_interventions_gdr

    slots = hitl_review_slots(ws, view_profile)
    acc_recs = emit_account_records(ws, view_profile)
    knapsack = select_interventions_gdr(acc_recs, slots)
    if knapsack.get("selected"):
        st.caption(
            f"Intervention knapsack: {len(knapsack['selected'])}/{slots} review slots — "
            f"expected savings ${knapsack['total_savings_usd']:,.0f}."
        )
        for rec in knapsack["selected"][:3]:
            subj = rec.get("subject", {})
            st.write(f"- `{subj.get('account_id', '—')}` · ${rec.get('economics', {}).get('primary_metric_usd', 0):,.0f}")

    section_kicker("Token-cost tail risk")
    from analytics.token_risk import (
        budget_breach_probability,
        daily_spend_series,
        pricing_shock_simulation,
        token_cost_var,
    )

    daily = daily_spend_series(ws)
    shock_pct = st.slider("Oracle price shock %", 0, 100, 0, key="econ_shock") / 100.0
    risk = pricing_shock_simulation(ws, shock_pct) if shock_pct else token_cost_var(daily)
    mean_daily = float(daily.mean()) if not daily.empty else 0.0
    budget = st.number_input("Daily budget USD", value=round(2 * mean_daily) if mean_daily else 500.0)
    breach = budget_breach_probability(daily, budget) if not daily.empty else 0.0
    v1, v2, v3 = st.columns(3)
    v1.metric("Daily VaR 5%", f"${risk.get('var', 0):,.0f}")
    v2.metric("Daily CVaR 5%", f"${risk.get('cvar', 0):,.0f}")
    v3.metric("P(day > budget)", f"{breach:.0%}")
    if not daily.empty:
        import plotly.graph_objects as go

        fig_hist = go.Figure(go.Histogram(x=daily.values, nbinsx=20))
        fig_hist.add_vline(x=risk.get("var", 0), line_color="#dc2626", annotation_text="VaR")
        fig_hist.add_vline(x=budget, line_color="#64748b", annotation_text="Budget")
        fig_hist.update_layout(height=320, margin=dict(l=40, r=40, t=40, b=40))
        st.plotly_chart(fig_hist, use_container_width=True)
    st.caption("VaR = a bad day; CVaR = how bad the bad days are. Synthetic run costs.")

    section_kicker("Willingness-to-pay priors")
    from analytics.demand_model import (
        fit_and_cache_demand,
        get_demand_fit,
        pypricing_available,
    )
    from analytics.demand_panel import build_demand_panel, panel_power
    from analytics.wtp_priors import (
        churn_after_price_change,
        expansion_lift_after_verified,
        wtp_cap_from_data,
    )
    from core.workspace import sync_workspace_to_session
    from ui.evidence_chrome import render_claim_badge, render_underpowered_callout

    wtp = wtp_cap_from_data(ws, view_profile)
    churn = churn_after_price_change(ws)
    lift = expansion_lift_after_verified(ws)
    panel = build_demand_panel(ws)
    power = panel_power(panel)
    fit = get_demand_fit(ws)

    if pypricing_available():
        if not power["ok"]:
            render_underpowered_callout(" · ".join(power.get("reasons", [])))
        if st.button("Fit demand", key="econ_fit_demand"):
            with st.spinner("Sampling posterior…"):
                fit_and_cache_demand(ws, panel=panel, draws=300, tune=300, chains=2)
                sync_workspace_to_session(st.session_state, ws)
            st.success("Demand fit cached.")
            fit = get_demand_fit(ws)
    else:
        st.caption("Fitted demand: `pip install -r requirements-pricing.txt`")

    w1, w2, w3, w4 = st.columns(4)
    cap_disp = f"${wtp['cap_usd']:.2f}" if wtp.get("cap_usd") is not None else "—"
    w1.metric("Data-derived cap", cap_disp)
    w2.metric("Churn hazard (price change)", f"{churn.get('hazard_ratio') or '—'}")
    w3.metric("Expansion lift", f"{lift.get('lift_pct') or '—'}%")
    if fit and not fit.get("underpowered"):
        skus = fit.get("skus") or {}
        eps_vals = [s.get("elasticity_mean") for s in skus.values() if s.get("elasticity_mean") is not None]
        surplus_vals = [s.get("surplus_opt_usd") for s in skus.values() if s.get("surplus_opt_usd") is not None]
        w4.metric(
            "Fitted ε (median)",
            f"{sorted(eps_vals)[len(eps_vals) // 2]:.2f}" if eps_vals else "—",
        )
        if surplus_vals:
            st.caption(
                f"Surplus-opt lists (median): ${sorted(surplus_vals)[len(surplus_vals) // 2]:.2f} "
                f"across {len(surplus_vals)} SKUs"
            )
    else:
        w4.metric("Fitted demand", "—")

    if fit and not fit.get("underpowered"):
        render_claim_badge(fit.get("claim_type", "simulated"))
    else:
        render_claim_badge(wtp.get("claim_type", "associational"))
    if wtp.get("underpowered") and not (fit and not fit.get("underpowered")):
        render_underpowered_callout(wtp.get("detail", "insufficient n for WTP cap"))
    st.caption(
        "Rigorous mode uses surplus-opt list from demand_fit when cached; otherwise median MRR/list cap. "
        "Associational unless an experiment_id is present."
    )

section_kicker("Loop depth & waterfall")
col_a, col_b = st.columns(2)
with col_a:
    fig_loops = loop_histogram(ws.runs, float(ws.profile.get("max_loops_threshold", 8)))
    if fig_loops is not None:
        st.plotly_chart(fig_loops, use_container_width=True)
with col_b:
    fig_wf = cost_waterfall_sample(ws.runs)
    if fig_wf is not None:
        st.plotly_chart(fig_wf, use_container_width=True)

section_kicker("Power-user margin leakage (top 5%)")
pu = power_user_margin_table(ws)
if not pu.empty:
    st.dataframe(pu, use_container_width=True)

section_kicker("Static routing decisions")
if not ws.routing_decisions.empty:
    st.dataframe(ws.routing_decisions, use_container_width=True)
st.metric("Time to first production agent", resolve_metric("time_to_first_production_agent", ws)["display"])

arpu = float(ws.seats["seat_arpu_monthly"].mean()) if len(ws.seats) else 0.0
fig = run_cost_by_capability(ws.runs, ws.capabilities, arpu)
if fig is not None:
    section_kicker("Cost by capability")
    st.plotly_chart(fig, use_container_width=True)

records = emit_capability_records(ws, view_profile, filter_categories={"run_cost_blowout", "loop_exhaustion", "margin_leakage"}) + emit_account_records(ws, view_profile, filter_categories={"price"})
section_kicker("Decision records")
if not records:
    empty_records_caption("run_cost_blowout / margin_leakage")
for i, rec in enumerate(records[:5]):
    render_decision_card(rec, key_prefix=f"econ_{i}", show_override=False, workspace=ws)
