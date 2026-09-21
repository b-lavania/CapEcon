"""Data Connect — real ingest (OTel / CSV / Langfuse / Vision) onto the Workspace join."""

from pathlib import Path

import pandas as pd
import streamlit as st

from analytics.agentic_profile import get_preset
from core.workspace import build_workspace, get_workspace_from_session, sync_workspace_to_session
from data.adapters.csv import ingest_csv_table
from data.adapters.langfuse import ingest_langfuse_export
from data.adapters.otel import ingest_otel_export
from data.adapters.vision import ingest_vision_pack
from ui.decision_card import render_decision_card
from ui.explain import page_help
from ui.magazine import load_magazine_css, masthead, section_kicker

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead(
    "Setup",
    "Data Connect",
    "Upload traces, accounts, and outcomes. Prompt bodies are stripped. Synthetic demo remains available.",
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
]

uploaded: dict[str, pd.DataFrame] = dict(st.session_state.get("uploaded_tables") or {})

section_kicker("Traces")
otel_file = st.file_uploader("OTel JSONL export", type=["jsonl", "json"], key="otel_up")
langfuse_file = st.file_uploader("Langfuse JSON/JSONL export", type=["json", "jsonl"], key="lf_up")
col_a, col_b = st.columns(2)
with col_a:
    if st.button("Load golden OTel fixture", help="tests/fixtures/golden_otel.jsonl — includes prompt fields that must be scrubbed"):
        fixture = Path(__file__).parent.parent / "tests" / "fixtures" / "golden_otel.jsonl"
        tables = ingest_otel_export(fixture)
        uploaded["spans"] = tables["spans"]
        uploaded["runs"] = tables["runs"]
        st.session_state["uploaded_tables"] = uploaded
        st.session_state["ingest_source"] = "otel"
        st.success(f"Loaded fixture — {len(tables['spans'])} spans, {len(tables['runs'])} runs (scrubbed).")
        st.rerun()
with col_b:
    if otel_file is not None and st.button("Parse OTel upload"):
        tmp = Path("/tmp/churnos_otel.jsonl")
        tmp.write_bytes(otel_file.getvalue())
        tables = ingest_otel_export(tmp)
        uploaded["spans"] = tables["spans"]
        uploaded["runs"] = tables["runs"]
        st.session_state["uploaded_tables"] = uploaded
        st.session_state["ingest_source"] = "otel"
        st.success(f"{len(tables['spans'])} spans · {len(tables['runs'])} runs")
        st.rerun()

if langfuse_file is not None and st.button("Parse Langfuse export"):
    tmp = Path("/tmp/churnos_langfuse.json")
    tmp.write_bytes(langfuse_file.getvalue())
    tables = ingest_langfuse_export(tmp)
    uploaded["spans"] = tables["spans"]
    uploaded["runs"] = tables["runs"]
    st.session_state["uploaded_tables"] = uploaded
    st.session_state["ingest_source"] = "langfuse"
    st.success(f"Langfuse — {len(tables['spans'])} spans")
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
        root = Path(__file__).parent.parent / "tests" / "fixtures"
        pack = ingest_vision_pack(root / "vision_bakeoff_run.json", root / "vision_historic_jobs.jsonl")
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
        tmp_run = Path("/tmp/churnos_vision_run.json")
        tmp_run.write_bytes(vision_run.getvalue())
        tmp_jobs = None
        if vision_jobs is not None:
            tmp_jobs = Path("/tmp/churnos_vision_jobs.jsonl")
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
        tmp = Path(f"/tmp/churnos_{table}.csv")
        tmp.write_bytes(f.getvalue())
        try:
            uploaded[table] = ingest_csv_table(tmp, table)
            st.session_state["uploaded_tables"] = uploaded
            st.caption(f"{table}: {len(uploaded[table])} rows")
        except Exception as exc:
            st.error(f"{table}: {exc}")

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
preset = st.selectbox("Profile preset", ["assistant_heavy", "workspace_crm", "ops_mission"], index=0)
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
    st.success(
        f"Workspace ready — source `{ws.meta.get('data_source')}`, "
        f"{len(ws.runs)} runs, {len(getattr(ws, 'spans', []))} spans, {len(getattr(ws, 'outcomes', []))} outcomes."
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
