"""
Page 3: Conversion & Funnel
=============================
Funnel breakdown, A/B testing, and workspace experiment analysis.
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

from ui.explain import page_help
from ui.legacy_banner import render_legacy_banner
from ui.magazine import load_magazine_css, masthead
from ui.workspace_banner import require_workspace

load_magazine_css()
render_legacy_banner()
masthead(
    "Learn",
    "Experiments",
    "Workspace funnel tests, agentic power design, and CUPED-adjusted results.",
    cluster="after",
)
page_help("experiments", show_card_glossary=True)

PLOTLY_THEME = {
    "layout": {
        "plot_bgcolor": "rgba(0,0,0,0)",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "JetBrains Mono", "color": "#94a3b8", "size": 11},
        "xaxis": {"gridcolor": "rgba(255,255,255,0.05)", "zeroline": False, "linecolor": "rgba(255,255,255,0.1)"},
        "yaxis": {"gridcolor": "rgba(255,255,255,0.05)", "zeroline": False, "linecolor": "rgba(255,255,255,0.1)"},
        "margin": {"t": 40, "b": 40, "l": 40, "r": 20},
    }
}


def _workspace_econ(ws) -> dict[str, float]:
    """Teaching defaults from workspace when Business Model is not configured."""
    aov = 65.0
    if not ws.transactions.empty and "order_value" in ws.transactions.columns:
        aov = float(ws.transactions["order_value"].mean())
    priors = ws.profile.get("priors", {})
    gm = float(priors.get("gross_margin_pct", 0.60))
    if gm > 1:
        gm = gm / 100.0
    margin = aov * gm
    churn = float(priors.get("monthly_churn_base", 0.08))
    return {
        "aov": aov,
        "gross_margin_pct": gm * 100.0,
        "margin_per_active_monthly": margin,
        "clv_24": margin * 12.0,
        "monthly_churn_rate": churn,
    }


from analytics.product_metrics import conversion_lift_orders_margin, refund_exposure_rates
from analytics.conversion import (
    funnel_summary, segment_conversion, ab_test_significance,
    calculate_sample_size, estimate_test_duration, calculate_mde, calculate_power,
    validate_test_reliability, plan_multivariate_test, calculate_cro_metrics,
    bayesian_ab_test, revenue_at_stake, segment_revenue_gap, program_metrics,
    conversion_to_ltv_impact, experiment_roi,
)
from analytics.experimentation import (
    analyze_workspace_experiment,
    design_from_workspace,
    registry_entry_from_analysis,
    sequential_testing_warning,
)
from analytics.metrics import resolve_metric
from core.workspace import build_workspace, sync_workspace_to_session

ws = require_workspace(st.session_state, page_label="Experiments")
if ws is None:
    st.stop()

has_legacy_model = "model" in st.session_state and "model_summary" in st.session_state
if has_legacy_model:
    s = st.session_state["model_summary"]
    config = st.session_state.get("model_config", {})
else:
    s = _workspace_econ(ws)
    config = {"monthly_churn_rate": s["monthly_churn_rate"]}

resync_cols = st.columns([1, 1, 4])
with resync_cols[0]:
    new_seed = st.number_input("Workspace seed", 0, 99999, int(ws.seed), key="conv_ws_seed")
with resync_cols[1]:
    if st.button("Resync workspace", type="primary", key="conv_resync"):
        if has_legacy_model:
            sync_workspace_to_session(
                st.session_state,
                build_workspace(config, seed=int(new_seed)),
            )
        else:
            sync_workspace_to_session(
                st.session_state,
                build_workspace(ws.profile, seed=int(new_seed), n_sessions=5_000),
            )
        st.session_state["workspace_seed"] = int(new_seed)
        st.rerun()

if not has_legacy_model:
    st.caption(
        "Using workspace teaching defaults for AOV/margin. "
        "Configure **Business Model** (Legacy) for full causal-model read-through."
    )

funnel_df = ws.funnel
summary = funnel_summary(funnel_df)
_guard_tx = ws.transactions

cvr_metric = resolve_metric("session_to_purchase_cvr", ws)

# ── KPIs ──
total_s = summary.loc[summary["step"] == "Visit", "sessions"].iloc[0]
total_p = summary.loc[summary["step"] == "Purchase", "sessions"].iloc[0]
cvr = total_p / total_s * 100 if total_s > 0 else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("SESSIONS", f"{total_s:,}")
c2.metric("PURCHASES", f"{total_p:,}")
c3.metric("OVERALL CVR (catalog)", cvr_metric["display"])
c4.metric("CART ADD RATE", f"{summary.loc[summary['step'] == 'Add to Cart', 'conversion_rate'].iloc[0]}%")

# ── Tabs ──
tab_funnel, tab_design, tab_results, tab_program = st.tabs([
    "[ 01 ] FUNNEL & LEAKAGE",
    "[ 02 ] DESIGN",
    "[ 03 ] RESULTS (WORKSPACE TEST)",
    "[ 04 ] PROGRAM",
])

with tab_funnel:
    st.markdown('<div class="terminal-header">VISUAL FUNNEL BREAKDOWN</div>', unsafe_allow_html=True)
    fig = go.Figure(go.Funnel(
        y=summary["step"], x=summary["sessions"],
        textinfo="value+percent initial",
        marker=dict(color=["#00f2ff", "#8a2be2", "#ff9d00", "#14b8a6", "#f43f5e"]),
    ))
    fig.update_layout(**PLOTLY_THEME["layout"])
    st.plotly_chart(fig, use_container_width=True)

    # Drop-off analysis
    st.markdown('<div class="terminal-header">DROP-OFF ANALYSIS</div>', unsafe_allow_html=True)
    dropoff = summary[summary["drop_off_pct"] > 0].copy()
    fig_drop = px.bar(
        dropoff, x="step", y="drop_off_pct",
        color="drop_off_pct",
        color_continuous_scale=["#14b8a6", "#ff9d00", "#f43f5e"],
        labels={"step": "FUNNEL STEP", "drop_off_pct": "DROP-OFF %"},
    )
    fig_drop.update_layout(**PLOTLY_THEME["layout"], coloraxis_showscale=False)
    st.plotly_chart(fig_drop, use_container_width=True)

    st.markdown('<div class="terminal-header">REVENUE AT STAKE // WHAT EACH LEAK COSTS</div>', unsafe_allow_html=True)
    rev_stake = revenue_at_stake(funnel_df, aov=s["aov"], gross_margin_pct=s["gross_margin_pct"])
    fig_rev = px.bar(
        rev_stake, x="step", y="revenue_at_stake",
        color="revenue_at_stake",
        color_continuous_scale=["#14b8a6", "#ff9d00", "#f43f5e"],
        labels={"step": "FUNNEL STEP", "revenue_at_stake": "REVENUE LOST ($)"},
        text_auto=".0f",
    )
    fig_rev.update_layout(**PLOTLY_THEME["layout"], coloraxis_showscale=False)
    fig_rev.update_traces(textposition="outside", textfont_size=11)
    st.plotly_chart(fig_rev, use_container_width=True)
    st.caption("Revenue at stake = sessions lost × AOV × gross margin %. Fix the biggest bar first.")

    st.markdown('<div class="terminal-header">SEGMENT REVENUE LEAKAGE</div>', unsafe_allow_html=True)
    leak_dim = st.selectbox("Leakage dimension", ["device", "source"], key="exp_leak_dim")
    gap_df = segment_revenue_gap(
        funnel_df, segment_by=leak_dim, aov=s["aov"], gross_margin_pct=s["gross_margin_pct"]
    )
    if not gap_df.empty:
        fig_gap = px.bar(
            gap_df, x=leak_dim, y="revenue_gap",
            color="revenue_gap",
            color_continuous_scale=["#14b8a6", "#ff9d00", "#f43f5e"],
            labels={leak_dim: leak_dim.upper(), "revenue_gap": "REVENUE GAP ($)"},
        )
        fig_gap.update_layout(**PLOTLY_THEME["layout"], coloraxis_showscale=False)
        st.plotly_chart(fig_gap, use_container_width=True)

    st.markdown('<div class="terminal-header">CVR BY DEVICE CLASS</div>', unsafe_allow_html=True)
    dev_conv = segment_conversion(funnel_df, by="device")
    fig2 = px.bar(
        dev_conv, x="device", y="conversion_rate",
        color="device",
        color_discrete_sequence=["#00f2ff", "#8a2be2", "#ff9d00"],
        labels={"device": "DEVICE", "conversion_rate": "CONVERSION RATE"},
    )
    fig2.update_layout(**PLOTLY_THEME["layout"], showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<div class="terminal-header">CVR BY SOURCE</div>', unsafe_allow_html=True)
    src_conv = segment_conversion(funnel_df, by="source")
    fig3 = px.bar(
        src_conv, x="source", y="conversion_rate",
        color="source",
        color_discrete_sequence=["#00f2ff", "#8a2be2", "#ff9d00", "#14b8a6", "#f43f5e"],
        labels={"source": "SOURCE", "conversion_rate": "CONVERSION RATE"},
    )
    fig3.update_layout(**PLOTLY_THEME["layout"], showlegend=False)
    st.plotly_chart(fig3, use_container_width=True)

new_sess = int(cvr_metric["meta"].get("visits", 30_000))
baseline_cvr_frac = float(cvr_metric["value"] or cvr) / 100.0

with tab_design:
    st.markdown('<div class="terminal-header">WORKSPACE DESIGN PLANNER</div>', unsafe_allow_html=True)
    plan = design_from_workspace(ws, mde_relative=0.10)
    d1, d2, d3 = st.columns(3)
    d1.metric("Baseline CVR", f"{plan['baseline_cvr']*100:.2f}%")
    d2.metric("Per-variant N", f"{plan['sample_size']['sample_size_per_variant']:,}")
    d3.metric("Est. days", plan["duration"]["days_to_completion"])
    for w in plan["sample_size"].get("warnings", []) + plan["duration"].get("warnings", []):
        st.warning(w)
    st.caption(f"Assumes ~{plan['daily_traffic_assumed']:,} sessions/day from workspace funnel.")

    legacy_panels = st.expander(
        "Legacy Business Model panels (LTV / ROI read-through)",
        expanded=has_legacy_model,
    )
    with legacy_panels:
        st.markdown('<div class="terminal-header">CONVERSION RATE → REVENUE IMPACT</div>', unsafe_allow_html=True)
        st.markdown(
            '<p style="font-size: 0.82rem; color: #94a3b8; margin-bottom: 1rem;">'
            'If you improve a funnel step, how does that impact total cohort revenue? '
            'This connects your funnel optimization directly to the causal business model.'
            '</p>',
            unsafe_allow_html=True,
        )

        step_to_improve = st.selectbox("Funnel Step to Improve", ["Product View", "Add to Cart", "Checkout", "Purchase"], key="conv_step", help="Adjust this parameter to see its impact on the model.")
        improvement_pct = st.slider("Improvement (%)", 1, 50, 10, step=1, key="conv_improve", help="Adjust this parameter to see its impact on the model.")

        baseline_cvr = baseline_cvr_frac
        step_data = summary[summary["step"] == step_to_improve]
        if len(step_data) > 0:
            step_rate = step_data["conversion_rate"].iloc[0] / 100.0
            improved_rate = step_rate * (1 + improvement_pct / 100.0)
            if step_rate > 0:
                cvr_ratio = improved_rate / step_rate
                new_cvr = baseline_cvr * cvr_ratio
            else:
                new_cvr = baseline_cvr

            ltv_impact = conversion_to_ltv_impact(
                baseline_cvr=baseline_cvr * 100,
                improved_cvr=new_cvr * 100,
                monthly_sessions=new_sess,
                aov=s["aov"],
                gross_margin_pct=s["gross_margin_pct"],
                monthly_churn_rate=config.get("monthly_churn_rate", 0.08),
            )

            additional_customers = int(new_sess * (new_cvr - baseline_cvr))
            additional_monthly_rev = additional_customers * s["margin_per_active_monthly"]

            imp_cols = st.columns(4)
            imp_cols[0].metric("NEW CVR", f"{new_cvr * 100:.2f}%", f"+{(new_cvr - baseline_cvr) * 100:.2f}%")
            imp_cols[1].metric("ADDITIONAL CUSTOMERS", f"{additional_customers:,}")
            imp_cols[2].metric("MONTHLY MARGIN GAIN", f"${additional_monthly_rev:,.2f}")
            imp_cols[3].metric("24mo INCREMENTAL CLV", f"${ltv_impact['incremental_ltv_24mo']:,.2f}")

            st.caption(f"Each month, {ltv_impact['additional_customers_per_month']:.1f} additional customers enter the retention curve, generating ${ltv_impact['incremental_monthly_revenue']:,.2f}/mo in incremental margin.")

        st.markdown('<div class="terminal-header" style="margin-top: 2rem;">EXPERIMENT ROI CALCULATOR</div>', unsafe_allow_html=True)
        st.caption("Is this test worth the opportunity cost of not deploying immediately?")
        roi_col1, roi_col2 = st.columns(2)
        with roi_col1:
            exp_lift = st.number_input("EXPECTED LIFT (%)", 1.0, 100.0, 10.0, step=1.0, key="roi_lift")
        with roi_col2:
            exp_ss = st.number_input("SAMPLE SIZE PER VARIANT", 1000, 1000000, 5000, step=1000, key="roi_ss")
        try:
            roi_res = experiment_roi(
                baseline_cvr=baseline_cvr_frac,
                expected_lift_pct=exp_lift,
                sample_size_per_variant=exp_ss,
                daily_traffic=int(plan["daily_traffic_assumed"]),
                aov=s["aov"],
                gross_margin_pct=s["gross_margin_pct"],
            )
            roi_m1, roi_m2, roi_m3 = st.columns(3)
            roi_m1.metric("MONTHLY REVENUE GAIN", f"${roi_res['expected_monthly_revenue_gain']:,.2f}")
            roi_m2.metric("OPPORTUNITY COST", f"${roi_res['test_opportunity_cost']:,.2f}")
            roi_m3.metric("NET ROI (12mo)", f"${roi_res['net_roi_12mo']:,.2f}")
            if roi_res['net_roi_3mo'] > 0:
                st.success(roi_res['recommendation'])
            else:
                st.warning(roi_res['recommendation'])
        except Exception as e:
            st.error(f"ROI calculation error: {e}")

    st.markdown('<div class="terminal-header">SAMPLE SIZE & DURATION ESTIMATOR</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        base_cvr = st.number_input("BASELINE CVR (%)", 0.1, 100.0, 3.0, step=0.1, key="plan_base_cvr") / 100.0
    with c2:
        mde = st.number_input("MDE (RELATIVE %)", 1.0, 100.0, 10.0, step=1.0, key="plan_mde") / 100.0
    with c3:
        power = st.selectbox("POWER", [0.80, 0.90, 0.95], index=0, key="plan_power")
    with c4:
        daily_traffic = st.number_input("DAILY TRAFFIC", 100, 1000000, 1000, step=100, key="plan_traffic")

    try:
        ss_res = calculate_sample_size(base_cvr, mde, power=power)
        dur_res = estimate_test_duration(ss_res['total_sample_size'], daily_traffic, base_cvr)
        
        st.markdown(f"**Required Sample Size (per variant):** {ss_res['sample_size_per_variant']:,}")
        st.markdown(f"**Total Sample Size:** {ss_res['total_sample_size']:,}")
        st.markdown(f"**Estimated Duration:** {dur_res['days_to_completion']} days ({dur_res['weeks_to_completion']} weeks)")
        
        for w in ss_res.get('warnings', []) + dur_res.get('warnings', []):
            st.warning(w)
    except Exception as e:
        st.error(f"Calculation error: {e}")

    st.markdown('<div class="terminal-header" style="margin-top: 2rem;">STATISTICAL POWER & MDE ANALYZER</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**MDE Analyzer** (Given fixed sample size)")
        fixed_ss = st.number_input("SAMPLE SIZE PER VARIANT", 1000, 1000000, 5000, step=1000, key="mde_ss")
        try:
            mde_res = calculate_mde(base_cvr, fixed_ss, power=power)
            st.info(f"With {fixed_ss:,} users/variant, you can reliably detect a relative change of **{mde_res['mde_relative']*100:.2f}%**.")
            if mde_res.get('ecommerce_note'):
                st.caption(mde_res['ecommerce_note'])
        except Exception as e:
            st.error(f"Error: {e}")
            
    with c2:
        st.markdown("**Statistical Power Calculator**")
        effect_size = st.number_input("EXPECTED EFFECT SIZE (%)", 1.0, 100.0, 5.0, step=1.0, key="pow_effect") / 100.0
        try:
            pow_res = calculate_power(base_cvr, effect_size, fixed_ss)
            st.info(f"Statistical Power: **{pow_res['power_pct']:.1f}%** (Probability of detecting this effect)")
            for w in pow_res.get('warnings', []):
                st.warning(w)
        except Exception as e:
            st.error(f"Error: {e}")

    st.markdown('<div class="terminal-header" style="margin-top: 2rem;">AGENTIC EXPERIMENT DESIGN</div>', unsafe_allow_html=True)
    st.caption("Cluster-aware power for run/seat/account units — links to Lab · Power.")
    from analytics.experimentation import agentic_sample_size
    from analytics.evidence import is_rigorous_mode
    from ui.evidence_chrome import render_underpowered_callout

    ag1, ag2, ag3, ag4 = st.columns(4)
    with ag1:
        ag_baseline = st.slider("Baseline success rate", 0.05, 0.95, 0.72, 0.01, key="ag_base")
    with ag2:
        ag_mde_pp = st.slider("MDE (pp)", 0.5, 15.0, 3.0, 0.5, key="ag_mde")
    with ag3:
        ag_unit = st.selectbox("Unit", ["run", "seat", "account"], key="ag_unit")
    with ag4:
        ag_icc = st.slider("ICC (cluster)", 0.0, 0.5, 0.05, 0.01, key="ag_icc")

    ag_runs = st.number_input("Runs per unit", 1, 50, 5, key="ag_runs")
    ag_plan = agentic_sample_size(
        ag_baseline,
        ag_mde_pp / 100.0,
        unit=ag_unit,
        icc=ag_icc,
        runs_per_unit=int(ag_runs),
    )
    ap1, ap2, ap3 = st.columns(3)
    n_arm = ag_plan.get("sample_size_per_arm_clustered", 0)
    ap1.metric("Per-arm N", f"{n_arm:,}")
    ap2.metric("Design effect", f"{ag_plan.get('design_effect', 1.0):.2f}")
    ap3.metric("Total units", f"{n_arm * 2:,}")
    for w in ag_plan.get("warnings", []):
        st.warning(w)
    render_underpowered_callout(n_arm, max(100, n_arm))
    if is_rigorous_mode(ws.profile):
        st.caption("Rigorous mode — prefer seat/account ICC when outcomes cluster by account.")
    st.page_link("pages/31_Math_Lab_Power.py", label="Open Lab · Power", icon="🧪")

with tab_results:
    analysis = analyze_workspace_experiment(ws)
    counts = analysis["counts"]
    freq = analysis["frequentist"]
    bayes = analysis["bayesian"]
    srm = analysis["srm"]

    st.markdown('<div class="terminal-header">WORKSPACE EXPERIMENT (USER-ASSIGNED)</div>', unsafe_allow_html=True)
    st.dataframe(ws.experiment_outcomes, hide_index=True, use_container_width=True)

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Frequentist lift", f"{freq['lift_pct']:+.2f}%")
    r2.metric("p-value", f"{freq['p_value']:.4f}")
    r3.metric("P(variant wins)", f"{bayes['prob_b_better']:.1%}")
    r4.metric("SRM p-value", f"{srm['p_value']:.4f}")

    if not srm["passed"]:
        st.error(srm["message"])
    else:
        st.success(srm["message"])
    st.info(bayes["interpretation"])
    st.caption(analysis["notes"])

    st.markdown('<div class="terminal-header">CUPED VARIANCE REDUCTION</div>', unsafe_allow_html=True)
    from analytics.experimentation import cuped_adjust
    from analytics.panels import account_week_panel
    from analytics.evidence import is_rigorous_mode
    from ui.evidence_chrome import render_claim_badge
    import numpy as np

    runs = ws.runs
    assigns = ws.experiment_assignments
    exp_id = ws.default_experiment_id
    if not runs.empty and not assigns.empty and "variant" in assigns.columns:
        sub = assigns[assigns["experiment_id"] == exp_id] if "experiment_id" in assigns.columns else assigns
        ctrl_seats = set(sub.loc[sub["variant"] == "control", "seat_id"])
        var_seats = set(sub.loc[sub["variant"] == "variant", "seat_id"])
        ctrl_runs = runs[runs["seat_id"].isin(ctrl_seats)]
        var_runs = runs[runs["seat_id"].isin(var_seats)]
        if len(ctrl_runs) >= 2 and len(var_runs) >= 2:
            panel = account_week_panel(ws)
            pre_ctrl, pre_var = [], []
            for seat_id, grp in ctrl_runs.groupby("seat_id"):
                acc = ws.seats.loc[ws.seats["seat_id"] == seat_id]
                acc_id = acc["account_id"].iloc[0] if "account_id" in acc.columns and len(acc) else seat_id
                pw = panel[panel["account_id"] == acc_id]
                pre_ctrl.append(float(pw["outcome_success_rate"].mean()) if not pw.empty else 0.5)
            for seat_id, grp in var_runs.groupby("seat_id"):
                acc = ws.seats.loc[ws.seats["seat_id"] == seat_id]
                acc_id = acc["account_id"].iloc[0] if "account_id" in acc.columns and len(acc) else seat_id
                pw = panel[panel["account_id"] == acc_id]
                pre_var.append(float(pw["outcome_success_rate"].mean()) if not pw.empty else 0.5)
            y_ctrl = ctrl_runs.groupby("seat_id")["success"].mean().values
            y_var = var_runs.groupby("seat_id")["success"].mean().values
            n = min(len(y_ctrl), len(pre_ctrl), len(y_var), len(pre_var))
            if n >= 2:
                cuped = cuped_adjust(
                    np.array(y_ctrl[:n]),
                    np.array(y_var[:n]),
                    np.array(pre_ctrl[:n]),
                    np.array(pre_var[:n]),
                )
                raw_lift = (float(y_var.mean()) - float(y_ctrl.mean())) * 100
                c1, c2, c3 = st.columns(3)
                c1.metric("Raw lift (pp)", f"{raw_lift:+.2f}")
                adj = cuped.get("adjusted_lift")
                c2.metric("CUPED-adjusted lift (pp)", f"{adj * 100:+.2f}" if adj is not None else "—")
                c3.metric("Variance reduction", f"{cuped.get('variance_reduction_pct', 0):.1f}%")
    else:
        st.caption("CUPED requires workspace runs with experiment assignments.")

    if ws.default_experiment_id and srm.get("passed"):
        render_claim_badge("causal")
    elif is_rigorous_mode(ws.profile):
        st.caption("Claim: associational — SRM failed or no experiment_id.")

    gr = analysis["guardrails"]
    g1, g2 = st.columns(2)
    g1.metric("Guardrail refund %", f"{gr.get('refund_rate_orders_pct', '—')}%")
    g2.metric("Orders / buyer", f"{gr.get('orders_per_active_buyer', '—')}")

    if "cro_experiments" not in st.session_state:
        st.session_state["cro_experiments"] = []
    if st.button("Save workspace result to program registry", key="save_exp_registry"):
        entry = registry_entry_from_analysis(
            "Workspace funnel test",
            "Synthetic user-level assignment on shared warehouse",
            analysis,
        )
        st.session_state["cro_experiments"].append(entry)
        st.success(f"Added {entry['id']} to program registry.")

    st.markdown('<div class="terminal-header">MANUAL VALIDATOR (OVERRIDE COUNTS)</div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        cv = st.number_input("CONTROL VISITORS", 1000, 100000, counts["control_visitors"], key="val_cv")
    with c2:
        cc = st.number_input("CONTROL CONV.", 10, 10000, counts["control_conversions"], key="val_cc")
    with c3:
        vv = st.number_input("VARIANT VISITORS", 1000, 100000, counts["variant_visitors"], key="val_vv")
    with c4:
        vc = st.number_input("VARIANT CONV.", 10, 10000, counts["variant_conversions"], key="val_vc")
    with c5:
        duration = st.number_input("DURATION (DAYS)", 1, 365, 14, key="val_dur")

    if st.button("VALIDATE TEST", type="primary", key="val_run"):
        sig_res = ab_test_significance(cv, cc, vv, vc)
        val_res = validate_test_reliability(cv, cc, vv, vc, duration, sig_res['lift_pct'])
        
        m1, m2, m3 = st.columns(3)
        m1.metric("LIFT", f"{sig_res['lift_pct']:+.2f}%")
        m2.metric("P-VALUE", f"{sig_res['p_value']:.4f}")
        
        score_color = "#14b8a6" if val_res['reliability_score'] >= 80 else "#ff9d00" if val_res['reliability_score'] >= 60 else "#f43f5e"
        m3.markdown(f"<h3 style='color: {score_color}; margin: 0;'>RELIABILITY: {val_res['reliability_score']}/100</h3>", unsafe_allow_html=True)
        
        if val_res['is_reliable']:
            st.success("✓ TEST IS RELIABLE AND SIGNIFICANT")
        else:
            st.warning("⚠️ TEST HAS RELIABILITY CONCERNS")
            for w in val_res['warnings']:
                st.markdown(f"- {w}")
            for r in val_res['recommendations']:
                st.markdown(f"💡 {r}")

        st.markdown('<div class="terminal-header" style="margin-top: 1.5rem;">BAYESIAN A/B TEST</div>', unsafe_allow_html=True)
        bayes_res = bayesian_ab_test(cv, cc, vv, vc)
        b1, b2, b3, b4 = st.columns(4)
        prob_color = "#14b8a6" if bayes_res['prob_b_better'] >= 0.95 else "#ff9d00" if bayes_res['prob_b_better'] >= 0.80 else "#94a3b8"
        b1.markdown(f"<h3 style='color: {prob_color}; margin: 0;'>P(Variant > Control): {bayes_res['prob_b_better']:.1%}</h3>", unsafe_allow_html=True)
        b2.metric("EXPECTED LIFT", f"{bayes_res['expected_lift_pct']:+.2f}%")
        b3.metric("95% CREDIBLE INT.", f"[{bayes_res['credible_interval'][0]:+.2f}%, {bayes_res['credible_interval'][1]:+.2f}%]")
        b4.metric("EXPECTED LOSS", f"{bayes_res['expected_loss_pct']:.3f}%")
        st.info(bayes_res['interpretation'])

    st.markdown('<div class="terminal-header" style="margin-top: 2rem;">EXPERIMENT → BUSINESS READ-THROUGH</div>', unsafe_allow_html=True)

    rtl = st.slider(
        "Hypothetical lift on funnel CVR (relative %)",
        min_value=-15,
        max_value=40,
        value=10,
        step=1,
        key="exp_read_rel_lift",
    )

    read = conversion_lift_orders_margin(
        baseline_cvr_pct=float(cvr_metric["value"] or cvr),
        relative_lift_pct=float(rtl),
        baseline_sessions=int(new_sess),
        margin_per_incremental_buyer_monthly=float(s["margin_per_active_monthly"]),
        buyer_clv_24=float(s["clv_24"]),
    )

    rg1, rg2, rg3 = st.columns(3)

    rg1.metric("Δ session buyers approx", f"{read['delta_additional_session_buyers_approx']:,.4f}")

    rg2.metric("Δ monthly margin (model)", f"${read['estimated_monthly_margin_gain_usd']:,.2f}")

    rg3.metric("Δ 24mo modeled value", f"${read['estimated_total_clv_gain_24m_usd']:,.2f}")

    st.warning(read["ratio_metric_notes"])

    st.caption(
        "**Ratio metrics:** if your test changes bounce / sessions-per-users, quoting only session conversion mis-states incremental buyers."
    )

    ref = refund_exposure_rates(_guard_tx)

    g1, g2 = st.columns(2)

    rr_main = ref.get("refund_rate_all_orders_pct")

    g1.metric(
        "Guardrail │ refund mix (txn table)",
        "—" if rr_main is None or (isinstance(rr_main, float) and pd.isna(rr_main)) else f"{rr_main:.2f}%",
    )

    gd = ref.get("refund_rate_discounted_orders_pct")

    g2.metric(
        "Guardrail │ refunds on discounted orders",
        "—" if gd is None or (isinstance(gd, float) and pd.isna(gd)) else f"{gd:.2f}%",
    )

    st.caption(
        "Guardrail mix uses a seeded synthetic transactional slice—in production, reconcile with refunds and promotions fact tables."
    )

                
    st.markdown('<div class="terminal-header" style="margin-top: 2rem;">MULTIVARIATE TEST (MVT) PLANNER</div>', unsafe_allow_html=True)
    mvt_base_cvr = st.number_input("BASELINE CVR (%)", 0.1, 100.0, 3.0, step=0.1, key="mvt_base") / 100.0
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Element 1: Headline**")
        n_head = st.number_input("Number of variations (incl. Control)", 1, 10, 3, key="mvt_h")
    with c2:
        st.markdown("**Element 2: Button Color**")
        n_btn = st.number_input("Number of variations (incl. Control)", 1, 10, 2, key="mvt_b")
        
    try:
        elements = [{'name': 'headline', 'n_variations': n_head}, {'name': 'button_color', 'n_variations': n_btn}]
        mvt_res = plan_multivariate_test(mvt_base_cvr, elements)
        st.info(f"Total Combinations: **{mvt_res['total_combinations']}** | Sample Size per combination: **{mvt_res['sample_size_per_combination']:,}** | Total Sample Size: **{mvt_res['total_sample_size']:,}**")
        for w in mvt_res.get('warnings', []):
            st.warning(w)
    except Exception as e:
        st.error(f"Error planning MVT: {e}")

    st.markdown('<div class="terminal-header" style="margin-top: 2rem;">CRO METRICS DASHBOARD</div>', unsafe_allow_html=True)
    try:
        cro_metrics = calculate_cro_metrics(funnel_df)
        cm1, cm2, cm3 = st.columns(3)
        cm1.metric("BOUNCE RATE", f"{cro_metrics['bounce_rate']:.1f}%")
        cm2.metric("ABOVE-FOLD ENGAGEMENT", f"{cro_metrics['above_fold_engagement']:.1f}%")
        cm3.metric("AVG TIME ON PAGE", f"{cro_metrics['avg_time_on_page']:.1f}s")
    except Exception as e:
        st.info("💡 Additional CRO metrics (bounce rate, time on page) require extended event tracking data. Current tracking only records funnel progression.")

with tab_program:
    if "cro_experiments" not in st.session_state:
        st.session_state["cro_experiments"] = []
    experiments = st.session_state["cro_experiments"]
    warn = sequential_testing_warning(sum(1 for e in experiments if e.get("status") == "active"))
    if warn:
        st.warning(warn)
    metrics = program_metrics(experiments)
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Total tests", metrics["total_experiments"])
    p2.metric("Win rate", f"{metrics['win_rate_pct']:.1f}%")
    p3.metric("Avg lift", f"{metrics['avg_lift_pct']:+.2f}%")
    p4.metric("Cumulative $/mo", f"${metrics['cumulative_monthly_revenue_impact']:,.2f}")
    if experiments:
        st.dataframe(pd.DataFrame(experiments), hide_index=True, use_container_width=True)
    st.caption("Full program analytics also live on **CRO Program Dashboard** (legacy route).")
