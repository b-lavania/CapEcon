"""
Page 0: Business Model Configuration
======================================
The unified input screen : define your business so CapEcon can reason about it.
"""

import streamlit as st
from pathlib import Path

# ── Load CSS ──
css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

from ui.legacy_banner import render_legacy_banner
render_legacy_banner()

from analytics.causal_model import BusinessModel, TEMPLATES

# ── Header ──
st.markdown('<div class="terminal-header">SYSTEM CONFIG // BUSINESS MODEL DEFINITION</div>', unsafe_allow_html=True)
st.markdown('<h1 class="gradient-text">Business Model</h1>', unsafe_allow_html=True)

with st.expander("Concept Playbook: How to use this page"):
    st.markdown('''
    **Overview:** This page provides causal insights into your metrics.
    **How to use:** Adjust the inputs in the sidebar or main area to simulate different business scenarios. 
    Pay attention to the outputs with tooltips for detailed definitions. All metrics are connected to the central causal model.
    ''')

st.markdown(
    '<p style="max-width: 700px; margin-bottom: 2rem;">'
    'Define your business archetype. CapEcon will propagate these inputs through the '
    'full causal chain : from acquisition cost to lifetime value : so every dashboard '
    'reflects <em>your</em> economics.'
    '</p>',
    unsafe_allow_html=True,
)

# ── Business Type Selector ──
st.markdown('<div class="terminal-header">STEP 1 // BUSINESS TYPE</div>', unsafe_allow_html=True)

btype_col, template_col = st.columns([2, 3])
with btype_col:
    business_type = st.selectbox("Business Type",
        list(TEMPLATES.keys()),
        index=0,
        key="bm_business_type",
        help="Controls which metrics are relevant. Marketplace shows take rate & seller metrics; SaaS uses monthly subscription logic.",
    )

# Load template defaults for the selected type
template = TEMPLATES[business_type]

# Initialize config from template if not in session state, or if type changed
if "bm_config" not in st.session_state or st.session_state.get("_bm_type_prev") != business_type:
    st.session_state["bm_config"] = dict(template)
    st.session_state["_bm_type_prev"] = business_type

with template_col:
    st.markdown(
        f"""
        <div class="techno-card" style="padding: 1rem; margin-top: 0.2rem;">
            <span style="font-family: 'JetBrains Mono'; font-size: 0.7rem; color: #ff9d00;">
                TEMPLATE LOADED: {business_type.upper()}
            </span>
            <p style="font-size: 0.8rem; margin: 0.3rem 0 0;">
                Defaults are industry-typical starting points. Adjust below to match your business.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Section: Acquisition ──
st.markdown('<div class="terminal-header" style="margin-top: 2rem;">STEP 2 // ACQUISITION ECONOMICS</div>', unsafe_allow_html=True)

acq1, acq2, acq3, acq4 = st.columns(4)
with acq1:
    cohort_size = st.number_input("Cohort Size",
        100, 500000,
        int(template.get("cohort_size", 5000)),
        step=500,
        key="bm_cohort_size",
        help="Number of new customers in a cohort period (monthly).",
    )
with acq2:
    cac_paid = st.number_input("CAC : Paid ($)",
        0.0, 1000.0,
        float(template.get("cac_paid", 35.0)),
        step=1.0,
        key="bm_cac_paid",
        help="Average cost to acquire a customer through paid channels.",
    )
with acq3:
    cac_organic = st.number_input("CAC : Organic ($)",
        0.0, 500.0,
        float(template.get("cac_organic", 8.0)),
        step=1.0,
        key="bm_cac_organic",
        help="Average cost to acquire a customer through organic channels (content, SEO, etc.).",
    )
with acq4:
    paid_mix = st.slider("Paid Channel Mix (%)",
        0, 100,
        int(template.get("paid_mix", 0.45) * 100),
        step=5,
        key="bm_paid_mix",
        help="What percentage of your customers come from paid channels?",
    )

# ── Section: Retention & Churn ──
st.markdown('<div class="terminal-header" style="margin-top: 2rem;">STEP 3 // RETENTION & CHURN DYNAMICS</div>', unsafe_allow_html=True)

ret1, ret2, ret3, ret4 = st.columns(4)
with ret1:
    monthly_churn = st.slider("Monthly Churn Rate (%)",
        0.5, 40.0,
        float(template.get("monthly_churn_rate", 0.08) * 100),
        step=0.5,
        key="bm_monthly_churn",
        help="Average percentage of active customers lost each month.",
    )
    from core.workspace import get_workspace_from_session
    from analytics.causal_model import calibrate_churn_from_warehouse
    from analytics.evidence import is_rigorous_mode

    _ws = get_workspace_from_session(st.session_state)
    if _ws and is_rigorous_mode(_ws.profile):
        cal = calibrate_churn_from_warehouse(_ws, _ws.profile)
        if cal.get("calibrated"):
            st.caption(f"Calibrated from warehouse: {cal['monthly_churn_rate']:.1%}")
with ret2:
    subscribe_pct = st.slider("Subscribe & Save (%)",
        0, 100,
        int(template.get("subscribe_save_pct", 0.0) * 100),
        step=5,
        key="bm_subscribe_pct",
        help="Fraction of customers enrolled in a subscription program (reduces churn).",
    )
with ret3:
    sub_churn_reduction = st.slider("Subscriber Churn Reduction (%)",
        0, 100,
        int(template.get("subscriber_churn_reduction", 0.80) * 100),
        step=5,
        key="bm_sub_reduction",
        help="How much less subscribers churn vs non-subscribers.",
    )
with ret4:
    reactivation = st.slider("Reactivation Rate (%)",
        0.0, 20.0,
        float(template.get("reactivation_rate", 0.02) * 100),
        step=0.5,
        key="bm_reactivation",
        help="Percentage of churned customers who reactivate each month.",
    )

# Segment churn multipliers
with st.expander("Segment Churn Multipliers", expanded=False):
    st.markdown(
        "Multipliers applied to the base churn rate per segment. "
        "A multiplier of 1.6× means Budget customers churn 60% faster than average.",
    )
    seg_cols = st.columns(4)
    seg_mults = {}
    default_mults = template.get("segment_churn_multipliers", {})
    default_weights = template.get("segment_weights", {})
    for i, (seg, default_m) in enumerate(default_mults.items()):
        with seg_cols[i % 4]:
            seg_mults[seg] = st.number_input(
                f"{seg} churn ×",
                0.1, 5.0,
                float(default_m),
                step=0.1,
                key=f"bm_seg_mult_{seg}",
            )

    seg_wt_cols = st.columns(4)
    seg_weights = {}
    for i, (seg, default_w) in enumerate(default_weights.items()):
        with seg_wt_cols[i % 4]:
            seg_weights[seg] = st.slider(
                f"{seg} weight (%)",
                0, 100,
                int(default_w * 100),
                step=5,
                key=f"bm_seg_wt_{seg}",
            )
    # Normalize weights
    total_wt = sum(seg_weights.values())
    if total_wt > 0:
        seg_weights = {k: v / total_wt for k, v in seg_weights.items()}

# ── Section: Monetization ──
st.markdown('<div class="terminal-header" style="margin-top: 2rem;">STEP 4 // MONETIZATION & UNIT ECONOMICS</div>', unsafe_allow_html=True)

mon1, mon2, mon3 = st.columns(3)
with mon1:
    aov = st.number_input("Avg Order Value ($)",
        1.0, 10000.0,
        float(template.get("aov", 65.0)),
        step=5.0,
        key="bm_aov",
        help="Average revenue per transaction.",
    )
with mon2:
    frequency = st.number_input("Purchase Freq (orders/mo)",
        0.1, 30.0,
        float(template.get("purchase_frequency", 1.8)),
        step=0.1,
        key="bm_frequency",
        help="Average number of orders per active customer per month.",
    )
with mon3:
    cogs_pct = st.slider("COGS (%)",
        0, 90,
        int(template.get("cogs_pct", 0.40) * 100),
        step=5,
        key="bm_cogs",
        help="Cost of goods sold as a percentage of AOV.",
    )

mon4, mon5, mon6, mon7 = st.columns(4)
with mon4:
    shipping = st.number_input("Shipping Cost ($)",
        0.0, 50.0,
        float(template.get("shipping_cost", 5.0)),
        step=0.5,
        key="bm_shipping",
        help="Average shipping cost per order.",
    )
with mon5:
    refund_rate = st.slider("Refund Rate (%)",
        0, 50,
        int(template.get("refund_rate", 0.05) * 100),
        step=1,
        key="bm_refund",
        help="Percentage of orders that get refunded.",
    )
with mon6:
    disc_freq = st.slider("Discount Frequency (%)",
        0, 100,
        int(template.get("discount_frequency", 0.25) * 100),
        step=5,
        key="bm_disc_freq",
        help="Percentage of orders where a discount is applied.",
    )
with mon7:
    disc_depth = st.slider("Discount Depth (%)",
        0, 80,
        int(template.get("discount_depth", 0.15) * 100),
        step=5,
        key="bm_disc_depth",
        help="Average size of discount when one is applied.",
    )

# ── Section: Marketplace-specific ──
is_marketplace = business_type == "Marketplace"
if is_marketplace:
    st.markdown('<div class="terminal-header" style="margin-top: 2rem;">STEP 5 // MARKETPLACE ECONOMICS</div>', unsafe_allow_html=True)
    mp1, mp2, mp3, mp4 = st.columns(4)
    with mp1:
        take_rate = st.slider("Take Rate (%)",
            1, 50,
            int(template.get("take_rate", 0.15) * 100),
            step=1,
            key="bm_take_rate",
        )
    with mp2:
        buyer_fee = st.slider("Buyer Fee Split (%)",
            0, 100,
            int(template.get("buyer_fee_split", 0.40) * 100),
            step=5,
            key="bm_buyer_fee",
        )
    with mp3:
        fixed_fee = st.number_input("Fixed Fee / Txn ($)",
            0.0, 10.0,
            float(template.get("fixed_fee_per_txn", 0.0)),
            step=0.05,
            key="bm_fixed_fee",
        )
    with mp4:
        n_sellers = st.number_input("Seller Count",
            10, 100000,
            int(template.get("n_sellers", 500)),
            step=50,
            key="bm_n_sellers",
        )

# ──────────────────────────────────────────────
#  Build & Run Model
# ──────────────────────────────────────────────

st.markdown("---")

run_col, status_col = st.columns([1, 3])
with run_col:
    run_model = st.button(" Run Model", type="primary", key="bm_run")

# Assemble config dict from all widget values
def _assemble_config() -> dict:
    cfg = dict(template)
    cfg["business_type"] = business_type
    cfg["cohort_size"] = cohort_size
    cfg["cac_paid"] = cac_paid
    cfg["cac_organic"] = cac_organic
    cfg["paid_mix"] = paid_mix / 100.0
    cfg["monthly_churn_rate"] = monthly_churn / 100.0
    cfg["subscribe_save_pct"] = subscribe_pct / 100.0
    cfg["subscriber_churn_reduction"] = sub_churn_reduction / 100.0
    cfg["reactivation_rate"] = reactivation / 100.0
    cfg["segment_churn_multipliers"] = seg_mults
    cfg["segment_weights"] = seg_weights
    cfg["aov"] = aov
    cfg["purchase_frequency"] = frequency
    cfg["cogs_pct"] = cogs_pct / 100.0
    cfg["shipping_cost"] = shipping
    cfg["refund_rate"] = refund_rate / 100.0
    cfg["discount_frequency"] = disc_freq / 100.0
    cfg["discount_depth"] = disc_depth / 100.0
    if is_marketplace:
        cfg["take_rate"] = take_rate / 100.0
        cfg["buyer_fee_split"] = buyer_fee / 100.0
        cfg["fixed_fee_per_txn"] = fixed_fee
        cfg["n_sellers"] = n_sellers
    return cfg


# Auto-run on first load if no model exists yet
if run_model or "model" not in st.session_state:
    config = _assemble_config()
    model = BusinessModel(config)
    st.session_state["model"] = model
    st.session_state["model_config"] = config
    st.session_state["model_summary"] = model.compute_summary()

    from core.workspace import build_workspace, sync_workspace_to_session

    ws_seed = int(st.session_state.get("workspace_seed", 42))
    workspace = build_workspace(config, seed=ws_seed)
    sync_workspace_to_session(st.session_state, workspace)

    with status_col:
        st.success("Model + analytics workspace synced. Open **Executive Summary** or **Experimentation Hub**.")

if "workspace" not in st.session_state and "model_config" in st.session_state:
    from core.workspace import build_workspace, sync_workspace_to_session

    ws_seed = int(st.session_state.get("workspace_seed", 42))
    sync_workspace_to_session(
        st.session_state,
        build_workspace(st.session_state["model_config"], seed=ws_seed),
    )

# ── Quick Preview ──
if "model_summary" in st.session_state:
    s = st.session_state["model_summary"]
    st.markdown('<div class="terminal-header" style="margin-top: 1rem;">MODEL PREVIEW</div>', unsafe_allow_html=True)
    prev_cols = st.columns(6)
    prev_cols[0].metric("HEALTH SCORE", f"{s['health_score']}/100")
    prev_cols[1].metric("CLV (24mo)", f"${s['clv_24']:,.2f}")
    prev_cols[2].metric("BLENDED CAC", f"${s['cac']:,.2f}")
    prev_cols[3].metric("LTV : CAC", f"{s['ltv_cac']}x")
    payback_label = f"M{s['payback_month']}" if s['payback_month'] else "Never"
    prev_cols[4].metric("PAYBACK", payback_label)
    prev_cols[5].metric("EFF. CHURN/mo", f"{s['monthly_churn_eff']}%")
