"""Integrations & hooks — risk-ordered actions, not auto-act."""

from pathlib import Path

import streamlit as st

from ontology.store import list_hooks, log_hook
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead(
    "Config",
    "Integrations",
    "Slack first, then require_review. I will not auto-act.",
)
page_help("integrations")

cfg = st.session_state.setdefault("integrations", {})

section_kicker("1. Slack / ticket (lowest risk)")
cfg["slack_webhook"] = st.text_input("Slack webhook URL", value=cfg.get("slack_webhook", ""))
if st.button("Log test Slack alert"):
    log_hook("slack_alert", detail={"webhook_configured": bool(cfg["slack_webhook"])})
    st.success("Logged. Delivery happens only when a webhook is configured in the partner VPC.")

section_kicker("2. Require review")
st.caption("Destructive GDRs already set `requires_review`. Inbox knapsack is the queue.")
st.page_link("pages/19_Decision_Inbox.py", label="Decision Inbox")

section_kicker("3. Incident (PagerDuty)")
cfg["pagerduty_routing"] = st.text_input("PagerDuty routing key", value=cfg.get("pagerduty_routing", ""), type="password")
if st.button("Log test incident"):
    log_hook("pagerduty", detail={"configured": bool(cfg["pagerduty_routing"])})
    st.success("Logged destructive-review incident stub.")

section_kicker("4. CI Version Gate")
st.code(
    "curl -sS -X POST http://127.0.0.1:8088/version-gate \\\n"
    "  -H 'content-type: application/json' \\\n"
    "  -d '{\"n_prev\":100,\"s_prev\":82,\"n_curr\":100,\"s_curr\":61,\"eval_delta\":-0.12}'",
    language="bash",
)
st.caption("Start the API: `uvicorn service.app:app --port 8088`")

section_kicker("5. Feature flags (read-only)")
cfg["flag_vendor"] = st.selectbox(
    "Vendor",
    ["none", "launchdarkly", "split", "statsig"],
    index=["none", "launchdarkly", "split", "statsig"].index(cfg.get("flag_vendor", "none")),
)
st.caption("churnOS recommends traffic weights on Version Gate. The flag product remains source of truth.")

section_kicker("Owner map (no login)")
st.json(
    {
        "growth_lead": "Alex (growth)",
        "product": "Sam (product)",
        "engineering": "Jordan (eng)",
        "founder": "Pat (ops lead)",
        "finance": "Morgan (finance)",
    }
)

section_kicker("Hook audit")
events = list_hooks(limit=20)
if not events:
    st.caption("No hook invocations yet.")
else:
    st.dataframe(events, use_container_width=True, hide_index=True)

st.session_state["integrations"] = cfg
