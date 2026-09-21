"""Sidebar teacher-map stepper — Setup → Call → Price → Lab → After."""

from __future__ import annotations

from typing import Any

import streamlit as st

from core.workspace import get_workspace_from_session

LOOP_STEPS: list[tuple[str, str]] = [
    ("setup", "Setup"),
    ("call", "Call"),
    ("price", "Price"),
    ("lab", "Lab"),
    ("after", "After"),
]


def _step_states(session_state: Any, *, highlight: str | None = None) -> dict[str, str]:
    """Return per-step status: done | current | blocked."""
    ws = get_workspace_from_session(session_state)
    records = session_state.get("growth_records") or []
    has_outcome = any(r.get("outcome") for r in records)

    states: dict[str, str] = {sid: "blocked" for sid, _ in LOOP_STEPS}

    if ws is None:
        states["setup"] = "current"
        current = highlight or "setup"
        if current == "setup":
            return states
        # Still no warehouse — everything after Setup stays blocked
        return states

    # Warehouse exists: Setup through Lab unlocked; After needs flywheel outcomes
    order = [s for s, _ in LOOP_STEPS]
    for sid in ("setup", "call", "price", "lab"):
        states[sid] = "done"
    states["after"] = "done" if has_outcome else "blocked"

    current = highlight or session_state.get("teacher_map_group") or "price"
    if current not in states:
        current = "price"
    if current == "after" and not has_outcome:
        current = "lab"

    for sid in order:
        if sid == current:
            states[sid] = "current"
            break
    return states


def render_loop_stepper(session_state: Any, *, highlight: str | None = None) -> None:
    """Sidebar progress strip aligned to teacher map."""
    if highlight:
        session_state["teacher_map_group"] = highlight
    states = _step_states(session_state, highlight=highlight)

    parts: list[str] = []
    for i, (sid, label) in enumerate(LOOP_STEPS):
        status = states.get(sid, "blocked")
        cls = f"mag-loop-step mag-loop-step--{status}"
        parts.append(f'<span class="{cls}" title="{label}">{label}</span>')
        if i < len(LOOP_STEPS) - 1:
            parts.append('<span class="mag-loop-arrow">→</span>')

    st.markdown(
        f'<div class="mag-loop-stepper" aria-label="Teacher map">'
        f'{" ".join(parts)}</div>',
        unsafe_allow_html=True,
    )
