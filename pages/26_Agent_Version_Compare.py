"""Agent Version Comparison — SPRT + rollback / monitor / ship."""

from pathlib import Path

import streamlit as st

from analytics.agent_version_compare import compare_agent_versions
from analytics.decisions import emit_capability_records
from analytics.evidence import is_rigorous_mode
from analytics.inference.confidence_sequences import cs_two_proportion
from ontology.exception_taxonomy import ACTIONS
from ui.evidence_chrome import render_underpowered_callout
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.workspace_banner import require_workspace

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead(
    "Decide",
    "Agent Version Comparison",
    "Should you roll back the latest agent version?",
)
page_help("experiments")
st.page_link("pages/24_Version_Gate.py", label="Prefer Version Gate (ship / hold / rollback)")

ws = require_workspace(st.session_state, page_label="Agent Version Comparison")
cmp = compare_agent_versions(ws)

section_kicker("Version comparison")
st.caption(f"Previous: `{cmp.get('previous_version', '—')}` · Current: `{cmp.get('current_version', '—')}`")

lights = {"red": "🔴", "green": "🟢", "yellow": "🟡", "grey": "⚪"}
tl = cmp.get("traffic_light", "yellow")
st.markdown(f"### {lights.get(tl, '🟡')} {cmp.get('recommendation', 'hold').upper()}")

if cmp.get("rows"):
    st.dataframe(cmp["rows"], use_container_width=True, hide_index=True)
    js_val = cmp.get("js_outcome_mix", 0)
    st.caption(
        f"JS(outcome mix current vs previous) = {js_val:.3f}",
        help="0 = same mix; ~0.1+ is a material shift.",
    )
else:
    st.info("Not enough version history on this seed.")

rec = cmp.get("recommendation", "hold")
st.markdown(f"**Recommendation:** `{rec}` — {cmp.get('reason', '')}")

sprt = cmp.get("sprt") or {}
with st.expander("Evidence vs peeking (sequential test)", expanded=False):
    if sprt:
        st.write(
            f"SPRT decision: **{sprt.get('decision')}** · LLR {sprt.get('llr')} "
            f"(bounds {sprt.get('boundary_lower')} to {sprt.get('boundary_upper')}) · "
            f"n={sprt.get('n_total')}"
        )
    if cmp.get("p_value") is not None:
        st.caption(f"Fixed-n two-proportion z-test p-value: {cmp['p_value']:.4f} (peeking inflates false positives)")
    if cmp.get("recommendation") == "hold":
        render_underpowered_callout(
            cmp.get("n_curr", 0) + cmp.get("n_prev", 0),
            60,
        )

cs_expanded = is_rigorous_mode(ws.profile)
with st.expander("Always-valid bounds (confidence sequence)", expanded=cs_expanded):
    st.caption("This interval stays valid if you peek every day. The p-value above does not.")
    cs = cs_two_proportion(
        cmp.get("s_prev", 0),
        cmp.get("n_prev", 0),
        cmp.get("s_curr", 0),
        cmp.get("n_curr", 0),
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("Δ success (pp)", f"{cs.get('delta', 0) * 100:+.1f}")
    m2.metric("CS 95% lo", f"{cs.get('lo', 0) * 100:+.1f}%")
    m3.metric("CS 95% hi", f"{cs.get('hi', 0) * 100:+.1f}%")
    series = cs.get("series") or []
    if series:
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[p["n"] for p in series],
            y=[p["delta"] for p in series],
            mode="markers",
            name="Δ",
        ))
        fig.add_trace(go.Scatter(
            x=[p["n"] for p in series] + [p["n"] for p in series][::-1],
            y=[p["hi"] for p in series] + [p["lo"] for p in series][::-1],
            fill="toself",
            fillcolor="rgba(59,130,246,0.2)",
            line=dict(color="rgba(255,255,255,0)"),
            name="CS band",
        ))
        fig.add_hline(y=0, line_dash="dash", line_color="#64748b")
        fig.update_layout(
            xaxis_title="Cumulative n",
            yaxis_title="Δ success rate",
            height=320,
            margin=dict(l=40, r=40, t=40, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
    if cs.get("lo", -1) <= 0 <= cs.get("hi", 1):
        st.caption("Do not ship or rollback on this peek — sequence still includes no-difference.")

with st.expander("Traffic allocation (YAML bandit policy)", expanded=False):
    from analytics.bandits import thompson_allocation

    caps = ws.capabilities["capability_id"].tolist() if not ws.capabilities.empty else []
    overlay = st.session_state.get("semantics_overlay")
    if caps:
        cap_pick = st.selectbox("Capability", caps, key="bandit_cap")
        alloc = thompson_allocation(ws, cap_pick, semantics_overlay=overlay)
        if alloc.get("recommended_traffic"):
            st.write(alloc["recommended_traffic"])
            st.caption(alloc.get("message", ""))
        if alloc.get("policy"):
            st.json(alloc["policy"])
        regret = alloc.get("regret") or {}
        if regret.get("cumulative_regret"):
            import pandas as pd

            st.line_chart(
                pd.DataFrame({
                    "round": regret.get("rounds", []),
                    "cumulative_regret": regret.get("cumulative_regret", []),
                }).set_index("round")
            )
            st.caption("Teaching regret vs known optimal arm (synthetic simulation).")

section_kicker("Emit capability GDR from recommendation")
overlay = st.session_state.get("semantics_overlay")
if st.button("Emit version decision record"):
    recs = emit_capability_records(ws, ws.profile, semantics_overlay=overlay)
    if recs:
        top = dict(recs[0])
        action = rec if rec in ACTIONS else "hold"
        top["decision"] = dict(top["decision"])
        top["decision"]["recommended_action"] = action
        top["decision"]["final_action"] = action
        st.session_state.setdefault("growth_records", []).insert(0, top)
        st.success(f"GDR updated with version recommendation: {action}")
    else:
        st.warning("No capability GDRs to attach recommendation.")
