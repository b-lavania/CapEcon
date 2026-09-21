"""In-page state sketches — triage / flywheel rows and decision ASCII (no mermaid)."""

from __future__ import annotations

from html import escape
from typing import Sequence

import streamlit as st

from ui.magazine import load_magazine_css

VERSION_GATE_ASCII = """\
  Version Gate (first match wins — not a cycle)

  [1] eval delta ≤ −10%          → hold   (fail)
  [2] projected CPSO over cap    → hold   (warn/fail)
  [3] canary / SPRT rollback     → rollback (fail)
  [4] underpowered / SPRT cont.  → hold   (warn)
  [5] else                       → ship"""

TWO_AXIS_ASCII = """\
  Exceptions this window
            │
            ▼
         Verdict
            │
       ┌────┴────┐
       ▼         ▼
  Ops action   Commercial action
  (runtime)    (price book)
  ship/hold/   raise_list /
  throttle/…   split_tier / …"""


def render_state_row(steps: Sequence[str], current: str | None = None) -> None:
    """CSS state strip. ``current`` highlights one step when it matches a step label."""
    load_magazine_css()
    cells: list[str] = []
    for i, step in enumerate(steps):
        cls = "mag-state-step"
        if current is not None and step == current:
            cls += " is-current"
        cells.append(f'<span class="{cls}">{escape(step)}</span>')
        if i < len(steps) - 1:
            cells.append('<span class="mag-state-arrow" aria-hidden="true">→</span>')
    st.markdown(
        f'<div class="mag-state-row" role="img" aria-label="State flow">'
        f'{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def render_ascii_sketch(text: str) -> None:
    load_magazine_css()
    # Streamlit rewrites bare <pre> into stMarkdownPre and drops custom classes.
    st.markdown(
        f'<div class="mag-diagram" role="img">{escape(text)}</div>',
        unsafe_allow_html=True,
    )


def render_triage_sketch(current: str | None = None) -> None:
    """Inbox triage: pending → in_review → resolved | overridden | deferred."""
    # Display ends as a branch: resolved | overridden | deferred share the last slot visually
    steps = ["pending", "in_review", "resolved | overridden | deferred"]
    highlight: str | None = None
    if current in ("pending", "in_review"):
        highlight = current
    elif current in ("resolved", "overridden", "deferred"):
        highlight = "resolved | overridden | deferred"
    render_state_row(steps, current=highlight)


def render_flywheel_sketch() -> None:
    """Binary lifecycle matching pages/20_Outcome_Flywheel.py."""
    render_state_row(["awaiting outcome", "written back"], current=None)


def render_version_gate_sketch() -> None:
    """Static tree matching evaluate_from_counts order — not bound to this seed."""
    render_ascii_sketch(VERSION_GATE_ASCII)


def render_two_axis_sketch() -> None:
    """Ops vs commercial exits from the same verdict."""
    render_ascii_sketch(TWO_AXIS_ASCII)


# Re-export for callers that want the constant
__all__ = [
    "render_state_row",
    "render_ascii_sketch",
    "render_triage_sketch",
    "render_flywheel_sketch",
    "render_version_gate_sketch",
    "render_two_axis_sketch",
]
