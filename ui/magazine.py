"""Magazine / editorial UI chrome for agentic CapEcon."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

_CSS_LOADED = False


def load_magazine_css() -> None:
    global _CSS_LOADED
    if _CSS_LOADED:
        return
    css_path = Path(__file__).parent.parent / "assets" / "style.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)
    _CSS_LOADED = True


def masthead(kicker: str, title: str, deck: str = "", *, cluster: str | None = None) -> None:
    """Magazine header. Pass ``cluster`` (setup|call|price|lab|after|config) for the orientation strip."""
    load_magazine_css()
    deck_html = f'<p class="mag-deck">{deck}</p>' if deck else ""
    st.markdown(
        f"""
        <header class="mag-masthead">
            <p class="mag-kicker">{kicker}</p>
            <h1 class="mag-title">{title}</h1>
            {deck_html}
        </header>
        """,
        unsafe_allow_html=True,
    )
    if cluster:
        from ui.teacher_map import render_orientation_strip

        render_orientation_strip(cluster)


def section_kicker(label: str) -> None:
    load_magazine_css()
    st.markdown(f'<p class="mag-section-kicker">{label}</p>', unsafe_allow_html=True)


def editorial_rule() -> None:
    st.markdown('<hr class="mag-rule" />', unsafe_allow_html=True)


PLOTLY_LAYOUT = {
    "plot_bgcolor": "#ffffff",
    "paper_bgcolor": "#faf9f7",
    "font": {"family": "DM Mono, monospace", "color": "#5c6370", "size": 11},
    "colorway": ["#0a5a46", "#ba7517", "#185fa5", "#1d9e75", "#0f1112"],
    "xaxis": {
        "gridcolor": "rgba(15, 17, 18, 0.06)",
        "zeroline": False,
        "linecolor": "#e8eaed",
        "tickfont": {"color": "#5c6370"},
    },
    "yaxis": {
        "gridcolor": "rgba(15, 17, 18, 0.06)",
        "zeroline": False,
        "linecolor": "#e8eaed",
        "tickfont": {"color": "#5c6370"},
    },
    "margin": {"t": 36, "b": 40, "l": 48, "r": 20},
}


def apply_plotly_theme(fig):
    """Apply Blavania layout to a Plotly figure."""
    fig.update_layout(**PLOTLY_LAYOUT)
    return fig
