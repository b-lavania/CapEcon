"""Data Connect — real ingest (OTel / CSV / Langfuse / Vision / econ-world) onto the Workspace join."""

from pathlib import Path

import pandas as pd
import streamlit as st

from analytics.agentic_profile import get_preset
from core.workspace import build_workspace, get_workspace_from_session, sync_workspace_to_session
from data.adapters.abm import ingest_abm_export
from data.adapters.csv import ingest_csv_table
from data.adapters.finance import ingest_finance_export
from data.adapters.langfuse import ingest_langfuse_export
from data.adapters.macro import ingest_macro_export
from data.adapters.market import ingest_market_export
from data.adapters.otel import ingest_otel_export
from data.adapters.rl import ingest_rl_export
from data.adapters.vision import ingest_vision_pack
from data.adapters.workflow import ingest_workflow_export
from ui.decision_card import render_decision_card
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

FIXTURE_ROOT = Path(__file__).parent.parent / "tests" / "fixtures"
ADAPTER_FIXTURES = FIXTURE_ROOT / "adapters"

load_magazine_css()
masthead(
    "Setup",
    "Data Connect",
    "Upload traces, market / workflow / sim exports, accounts, and outcomes. Prompt bodies are stripped. Synthetic demo remains available.",
    cluster="setup",
)
page_help("data_connect")

JOIN_TABLES = [
    ("accounts", "Paying org join"),
    ("runs", "Agent executions"),
    ("spans", "Metadata-only steps"),
    ("outcomes", "Verified business results"),
    ("subscriptions", "Revenue (CM-NRR)"),
    ("usage_events", "Serving cost"),
    ("approvals", "HITL"),
    ("eval_results", "Version Gate evals"),
    ("agent_transactions", "Marketplace txns"),
]

uploaded: dict[str, pd.DataFrame] = dict(st.session_state.get("uploaded_tables") or {})


def _apply_pack(pack: dict, source: str) -> None:
    tables = pack.get("tables") or pack
    for key, frame in tables.items():
        if isinstance(frame, pd.DataFrame):
            uploaded[key] = frame
    st.session_state["uploaded_tables"] = uploaded
    st.session_state["ingest_source"] = source
    if pack.get("meta"):
        st.session_state["ingest_meta"] = pack["meta"]


section_kicker("Traces")
otel_file = st.file_uploader("OTel JSONL export", type=["jsonl", "json"], key="otel_up")
langfuse_file = st.file_uploader("Langfuse JSON/JSONL export", type=["json", "jsonl"], key="lf_up")
langgraph_file = st.file_uploader("LangGraph node JSON", type=["json", "jsonl"], key="lg_up")
col_a, col_b, col_c = st.columns(3)
with col_a:
    if st.button("Load golden OTel fixture", help="tests/fixtures/golden_otel.jsonl — includes prompt fields that must be scrubbed"):
        tables = ingest_otel_export(FIXTURE_ROOT / "golden_otel.jsonl")
        uploaded["spans"] = tables["spans"]
        uploaded["runs"] = tables["runs"]
        st.session_state["uploaded_tables"] = uploaded
        st.session_state["ingest_source"] = "otel"
        st.success(f"Loaded fixture — {len(tables['spans'])} spans, {len(tables['runs'])} runs (scrubbed).")
        st.rerun()
with col_b:
    if otel_file is not None and st.button("Parse OTel upload"):
        tmp = Path("/tmp/capecon_otel.jsonl")
        tmp.write_bytes(otel_file.getvalue())
        tables = ingest_otel_export(tmp)
        uploaded["spans"] = tables["spans"]
        uploaded["runs"] = tables["runs"]
        st.session_state["uploaded_tables"] = uploaded
        st.session_state["ingest_source"] = "otel"
        st.success(f"{len(tables['spans'])} spans · {len(tables['runs'])} runs")
        st.rerun()
with col_c:
    if st.button("Load workflow fixture", help="tests/fixtures/adapters/workflow/sample.jsonl"):
        pack = ingest_workflow_export(ADAPTER_FIXTURES / "workflow" / "sample.jsonl")
        _apply_pack(pack, "workflow")
        st.success(f"Workflow fixture — {len(pack['tables']['runs'])} runs, {len(pack['tables']['spans'])} spans.")
        st.rerun()

if langfuse_file is not None and st.button("Parse Langfuse export"):
    tmp = Path("/tmp/capecon_langfuse.json")
    tmp.write_bytes(langfuse_file.getvalue())
    tables = ingest_langfuse_export(tmp)
    uploaded["spans"] = tables["spans"]
    uploaded["runs"] = tables["runs"]
    st.session_state["uploaded_tables"] = uploaded
    st.session_state["ingest_source"] = "langfuse"
    st.success(f"Langfuse — {len(tables['spans'])} spans")
    st.rerun()

if langgraph_file is not None and st.button("Parse LangGraph upload"):
    tmp = Path("/tmp/capecon_workflow.jsonl")
    tmp.write_bytes(langgraph_file.getvalue())
    pack = ingest_workflow_export(tmp, kind="langgraph")
    _apply_pack(pack, "workflow")
    st.success(f"LangGraph — {len(pack['tables']['runs'])} runs (retries land as spans).")
    st.rerun()

with st.expander("Live Langfuse pull (optional)", expanded=False):
    lf_url = st.text_input("Langfuse base URL")
    lf_key = st.text_input("API key", type="password")
    if st.button("Pull traces") and lf_url and lf_key:
        try:
            from data.adapters.langfuse import ingest_langfuse_project

            tables = ingest_langfuse_project(lf_url, lf_key)
            uploaded["spans"] = tables["spans"]
            uploaded["runs"] = tables["runs"]
            st.session_state["uploaded_tables"] = uploaded
            st.session_state["ingest_source"] = "langfuse"
            st.success(f"{len(tables['spans'])} spans")
        except Exception as exc:
            st.error(str(exc))

section_kicker("Market experiment")
st.caption("Simulated Magentic / MarketAgents-shaped export. Not a live marketplace connector.")
market_file = st.file_uploader("Market JSONL / JSON", type=["jsonl", "json"], key="market_up")
m1, m2 = st.columns(2)
with m1:
    if st.button("Load market fixture", help="tests/fixtures/adapters/market/sample.jsonl"):
        pack = ingest_market_export(ADAPTER_FIXTURES / "market" / "sample.jsonl")
        _apply_pack(pack, "market")
        st.success(f"Market fixture — {len(pack['tables']['agent_transactions'])} transactions.")
        st.rerun()
with m2:
    if market_file is not None and st.button("Parse market upload"):
        tmp = Path("/tmp/capecon_market.jsonl")
        tmp.write_bytes(market_file.getvalue())
        pack = ingest_market_export(tmp)
        _apply_pack(pack, "market")
        st.success(f"{len(pack['tables']['agent_transactions'])} transactions")
        st.rerun()

section_kicker("Vision Agent (two records)")
st.caption(
    "Bakeoff `cost_usd` → agent GDR floor (`estimated`). Historic `price_dollars` → "
    "move quote `charged_usd`. Not one card that subtracts $0.06 from $656."
)
vision_run = st.file_uploader("Bakeoff run.json", type=["json"], key="vision_run_up")
vision_jobs = st.file_uploader("Historic jobs JSONL", type=["jsonl", "json"], key="vision_jobs_up")
v_load, v_parse = st.columns(2)
with v_load:
    if st.button(
        "Load Vision fixtures",
        help="tests/fixtures/vision_bakeoff_run.json + vision_historic_jobs.jsonl",
    ):
        pack = ingest_vision_pack(FIXTURE_ROOT / "vision_bakeoff_run.json", FIXTURE_ROOT / "vision_historic_jobs.jsonl")
        uploaded["runs"] = pack["tables"]["runs"]
        uploaded["usage_events"] = pack["tables"]["usage_events"]
        st.session_state["uploaded_tables"] = uploaded
        st.session_state["ingest_source"] = "vision"
        st.session_state["vision_pack"] = {
            "agent_gdr": pack["agent_gdr"],
            "quote_records": pack["quote_records"],
        }
        st.success(
            f"Vision pack — agent floor ${pack['agent_gdr']['economics']['floor_usd']:.4f} estimated · "
            f"{len(pack['quote_records'])} move quotes (not copied onto the agent)."
        )
        st.rerun()
with v_parse:
    if vision_run is not None and st.button("Parse Vision upload"):
        tmp_run = Path("/tmp/capecon_vision_run.json")
        tmp_run.write_bytes(vision_run.getvalue())
        tmp_jobs = None
        if vision_jobs is not None:
            tmp_jobs = Path("/tmp/capecon_vision_jobs.jsonl")
            tmp_jobs.write_bytes(vision_jobs.getvalue())
        pack = ingest_vision_pack(tmp_run, tmp_jobs)
        uploaded["runs"] = pack["tables"]["runs"]
        uploaded["usage_events"] = pack["tables"]["usage_events"]
        st.session_state["uploaded_tables"] = uploaded
        st.session_state["ingest_source"] = "vision"
        st.session_state["vision_pack"] = {
            "agent_gdr": pack["agent_gdr"],
            "quote_records": pack["quote_records"],
        }
        st.success(f"{len(pack['tables']['runs'])} bakeoff runs · {len(pack['quote_records'])} quotes")
        st.rerun()

vision_pack = st.session_state.get("vision_pack") or {}
if vision_pack.get("agent_gdr"):
    agent = vision_pack["agent_gdr"]
    quotes = vision_pack.get("quote_records") or []
    render_decision_card(agent, key_prefix="vision_preview", show_override=False, expanded=True)
    quote_rows = [
        {
            "job": (q.get("subject") or {}).get("job_id"),
            "charged_usd": (q.get("economics") or {}).get("charged_usd"),
            "charged_basis": (q.get("economics") or {}).get("charged_basis"),
            "headline": q.get("include_in_headline_metrics"),
        }
        for q in quotes
    ]
    if quote_rows:
        st.dataframe(pd.DataFrame(quote_rows), use_container_width=True, hide_index=True)
    st.caption("Move invoices stay on quote records. They are not agent `list_usd`.")

section_kicker("Business join (CSV)")
csv_specs = [
    ("accounts", "accounts.csv"),
    ("outcomes", "outcomes.csv"),
    ("subscriptions", "subscriptions.csv"),
    ("usage_events", "usage_events.csv"),
    ("eval_results", "eval_results.csv"),
]
for table, label in csv_specs:
    f = st.file_uploader(label, type=["csv"], key=f"csv_{table}")
    if f is not None:
        tmp = Path(f"/tmp/capecon_{table}.csv")
        tmp.write_bytes(f.getvalue())
        try:
            uploaded[table] = ingest_csv_table(tmp, table)
            st.session_state["uploaded_tables"] = uploaded
            st.caption(f"{table}: {len(uploaded[table])} rows")
        except Exception as exc:
            st.error(f"{table}: {exc}")

with st.expander("More sim exports (RL, macro, ABM, finance)", expanded=False):
    st.caption("Simulated exports only. claim_type stays simulated. No upstream simulator is installed.")
    rl_file = st.file_uploader("RL episode JSONL", type=["jsonl", "json"], key="rl_up")
    r1, r2 = st.columns(2)
    with r1:
        if st.button("Load RL fixture"):
            pack = ingest_rl_export(ADAPTER_FIXTURES / "rl" / "sample.jsonl")
            _apply_pack(pack, "rl")
            st.success(f"RL — {len(pack['tables']['runs'])} episodes")
            st.rerun()
    with r2:
        if rl_file is not None and st.button("Parse RL upload"):
            tmp = Path("/tmp/capecon_rl.jsonl")
            tmp.write_bytes(rl_file.getvalue())
            pack = ingest_rl_export(tmp)
            _apply_pack(pack, "rl")
            st.success(f"{len(pack['tables']['runs'])} episodes")
            st.rerun()

    macro_file = st.file_uploader("Macro period JSONL", type=["jsonl", "json"], key="macro_up")
    a1, a2 = st.columns(2)
    with a1:
        if st.button("Load macro fixture"):
            pack = ingest_macro_export(ADAPTER_FIXTURES / "macro" / "sample.jsonl")
            _apply_pack(pack, "macro")
            st.success(f"Macro — {len(pack['tables']['outcomes'])} periods")
            st.rerun()
    with a2:
        if macro_file is not None and st.button("Parse macro upload"):
            tmp = Path("/tmp/capecon_macro.jsonl")
            tmp.write_bytes(macro_file.getvalue())
            pack = ingest_macro_export(tmp)
            _apply_pack(pack, "macro")
            st.success(f"{len(pack['tables']['outcomes'])} periods")
            st.rerun()

    abm_file = st.file_uploader("ABM scenario JSONL", type=["jsonl", "json"], key="abm_up")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("Load ABM fixture"):
            pack = ingest_abm_export(ADAPTER_FIXTURES / "abm" / "sample.jsonl")
            _apply_pack(pack, "abm")
            st.success(f"ABM — {len(pack['tables']['accounts'])} households")
            st.rerun()
    with b2:
        if abm_file is not None and st.button("Parse ABM upload"):
            tmp = Path("/tmp/capecon_abm.jsonl")
            tmp.write_bytes(abm_file.getvalue())
            pack = ingest_abm_export(tmp)
            _apply_pack(pack, "abm")
            st.success(f"{len(pack['tables']['accounts'])} households")
            st.rerun()

    fin_file = st.file_uploader("Finance blotter JSONL", type=["jsonl", "json"], key="fin_up")
    f1, f2 = st.columns(2)
    with f1:
        if st.button("Load finance fixture"):
            pack = ingest_finance_export(ADAPTER_FIXTURES / "finance" / "sample.jsonl")
            _apply_pack(pack, "finance")
            st.success(f"Finance — {len(pack['tables']['runs'])} trades")
            st.rerun()
    with f2:
        if fin_file is not None and st.button("Parse finance upload"):
            tmp = Path("/tmp/capecon_finance.jsonl")
            tmp.write_bytes(fin_file.getvalue())
            pack = ingest_finance_export(tmp)
            _apply_pack(pack, "finance")
            st.success(f"{len(pack['tables']['runs'])} trades")
            st.rerun()

    tok_file = st.file_uploader("Token routing JSONL (RouteLLM / FrugalGPT)", type=["jsonl", "json"], key="tok_up")
    t1, t2 = st.columns(2)
    with t1:
        if st.button("Load routing fixture"):
            from data.adapters.token_econ import ingest_token_econ_export

            pack = ingest_token_econ_export(ADAPTER_FIXTURES / "token_econ" / "routellm_cascade.jsonl")
            _apply_pack(pack, "token_econ")
            st.success(f"Routing — {len(pack['tables']['runs'])} queries")
            st.rerun()
    with t2:
        if tok_file is not None and st.button("Parse routing upload"):
            from data.adapters.token_econ import ingest_token_econ_export

            tmp = Path("/tmp/capecon_token_econ.jsonl")
            tmp.write_bytes(tok_file.getvalue())
            pack = ingest_token_econ_export(tmp)
            _apply_pack(pack, "token_econ")
            st.success(f"{len(pack['tables']['runs'])} queries")
            st.rerun()

section_kicker("Join status")
rows = []
for table, purpose in JOIN_TABLES:
    frame = uploaded.get(table)
    if table == "runs" and frame is None:
        frame = uploaded.get("agent_runs")
    n = 0 if frame is None else len(frame)
    rows.append({"table": table, "purpose": purpose, "rows": n, "joins": "yes" if n else "no"})
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
outcomes_df = uploaded.get("outcomes")
if outcomes_df is None or outcomes_df.empty:
    st.page_link("pages/02_Outcome_Definition.py", label="Outcomes empty → Outcome Definition Kit")

section_kicker("Build warehouse")
preset_options = ["assistant_heavy", "workspace_crm", "ops_mission", "marketplace_agentic", "agentic_commerce", "frugal_router"]
src_hint = st.session_state.get("ingest_source", "uploaded")
if src_hint == "token_econ":
    default_idx = preset_options.index("frugal_router")
elif src_hint == "market":
    default_idx = preset_options.index("agentic_commerce")
else:
    default_idx = 0
preset = st.selectbox("Profile preset", preset_options, index=default_idx)
if st.button("Merge into workspace", type="primary"):
    src = st.session_state.get("ingest_source", "uploaded")
    ws = build_workspace(
        get_preset(preset),
        seed=int(st.session_state.get("workspace_seed", 42)),
        n_sessions=5_000,
        data_source=src if uploaded else "synthetic",
        uploaded_tables=uploaded or None,
    )
    sync_workspace_to_session(st.session_state, ws)
    vision_pack = st.session_state.get("vision_pack") or {}
    if src == "vision" and vision_pack.get("agent_gdr"):
        st.session_state["growth_records"] = [vision_pack["agent_gdr"]]
        st.session_state["quote_records"] = vision_pack.get("quote_records") or []
    else:
        st.session_state["growth_records"] = []
        st.session_state.pop("quote_records", None)
    txn_n = len(getattr(ws, "agent_transactions", []))
    txn_bit = f", {txn_n} agent transactions" if txn_n else ""
    st.success(
        f"Workspace ready — source `{ws.meta.get('data_source')}`, "
        f"{len(ws.runs)} runs, {len(getattr(ws, 'spans', []))} spans, "
        f"{len(getattr(ws, 'outcomes', []))} outcomes{txn_bit}."
    )

if st.button("Use synthetic demo instead"):
    ws = build_workspace(get_preset(preset), seed=42, n_sessions=5_000, data_source="synthetic")
    sync_workspace_to_session(st.session_state, ws)
    st.session_state["growth_records"] = []
    st.session_state.pop("quote_records", None)
    st.session_state.pop("vision_pack", None)
    st.success("Synthetic teaching warehouse built.")

ws = get_workspace_from_session(st.session_state)
if ws is not None:
    st.caption(f"Current workspace source: `{ws.meta.get('data_source')}` · next: Version Gate or Outcome Definition.")
    st.page_link("pages/24_Version_Gate.py", label="Open Version Gate")
    if st.session_state.get("vision_pack"):
        st.page_link("pages/19_Decision_Inbox.py", label="Open Decision Inbox (quoting-agent GDR)")
    if not getattr(ws, "agent_transactions", pd.DataFrame()).empty:
        st.page_link("pages/35_Marketplace_Radar.py", label="Open Marketplace Radar")
