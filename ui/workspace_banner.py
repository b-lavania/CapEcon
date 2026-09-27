"""Shared workspace status strip + empty-state CTA for agentic pages."""

from __future__ import annotations

from typing import Any

import streamlit as st

from core.workspace import Workspace, get_workspace_from_session
from ui.loop_chrome import render_loop_stepper

PROFILE_PAGE = "pages/00_Agentic_Product_Profile.py"
PROFILE_CTA_LABEL = "Open Product Profile → Generate workspace"

REFERENCE_LINKS: list[tuple[str, str]] = [
    ("pages/7_Concepts.py", "Concepts"),
    ("pages/6_README.py", "Architecture"),
    ("pages/03_Teacher_Map.py", "Map atlas"),
    ("pages/21_Semantics_Console.py", "Semantics"),
    ("pages/22_Taxonomy_Browser.py", "Taxonomy"),
    ("pages/23_Record_Inspector.py", "Record Inspector"),
]


def empty_workspace_panel(*, page_label: str | None = None) -> None:
    """Shared empty-state copy + Profile CTA (non-blocking — caller may return or stop)."""
    target = page_label or "this screen"
    st.markdown(
        f"""
        <div class="mag-empty-workspace">
            <p class="mag-deck">
                Generate a teaching warehouse (traces × revenue join) before using
                <strong>{target}</strong>.
                Open <strong>Product Profile</strong>, pick a preset, then
                <strong>Generate workspace</strong> — or overlay files on
                <strong>Data Connect</strong>.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link(PROFILE_PAGE, label=PROFILE_CTA_LABEL, icon="▶️")


def render_sidebar_brand_and_status(session_state: Any) -> None:
    """Blavania brand block with live workspace status or missing-workspace hint."""
    ws = get_workspace_from_session(session_state)
    with st.sidebar:
        if ws is None:
            status_html = (
                '<p class="mag-sidebar-status mag-sidebar-status--empty">'
                "No workspace — Profile or Data Connect"
                "</p>"
            )
        else:
            preset = ws.profile.get("preset_id", "—")
            n_accounts = len(getattr(ws, "accounts", ws.workspaces))
            status_html = (
                f'<p class="mag-sidebar-status">'
                f"<span class=\"mag-sidebar-status-primary\">{preset}</span>"
                f" · seed {ws.seed}<br>"
                f"{len(ws.seats)} seats · {n_accounts} accounts"
                f"</p>"
            )

        st.markdown(
            f"""
            <div class="mag-sidebar-brand">
                <p class="mag-kicker">CapEcon</p>
                <p class="mag-sidebar-tagline">Decision-grade analytics loop</p>
                {status_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_loop_stepper(session_state)

        if ws is None:
            st.page_link(PROFILE_PAGE, label="→ Product Profile", icon="⚙️")
            st.page_link("pages/01_Data_Connect.py", label="→ Data Connect")
        elif st.button("Regenerate workspace", key="ws_banner_regen", type="secondary"):
            session_state.pop("workspace", None)
            session_state.pop("growth_records", None)
            st.rerun()


def render_sidebar_secondary_nav() -> None:
    """Collapsed Reference + Legacy + Standards links (pages registered as hidden routes)."""
    with st.sidebar:
        st.markdown('<div class="mag-sidebar-secondary">', unsafe_allow_html=True)
        with st.expander("Reference", expanded=False):
            for path, label in REFERENCE_LINKS:
                st.page_link(path, label=label)
        with st.expander("Legacy", expanded=False):
            st.page_link("pages/99_Legacy_Index.py", label="Legacy reference")
        with st.expander("Standards", expanded=False):
            st.page_link("pages/50_Standards_Export.py", label="Export formats")
            st.page_link("pages/51_ADP_Compliance.py", label="ADP compliance")
            st.page_link("pages/52_Policy_Card_Editor.py", label="Policy Cards")
        st.markdown("</div>", unsafe_allow_html=True)


# Backward-compatible alias
render_workspace_sidebar_chip = render_sidebar_brand_and_status


def require_workspace(
    session_state: Any,
    *,
    page_label: str = "this page",
) -> Workspace | None:
    """If workspace missing, show shared empty panel and stop."""
    ws = get_workspace_from_session(session_state)
    if ws is not None:
        return ws
    empty_workspace_panel(page_label=page_label)
    st.stop()
    return None


def empty_records_caption(filter_label: str) -> None:
    st.caption(
        f"No exceptions of type **{filter_label}** — classifiers may not have fired on this seed."
    )
