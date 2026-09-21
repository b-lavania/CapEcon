"""Map atlas — full IA diagrams (Reference). Orientation strips live on every page."""

from pathlib import Path

import streamlit as st

from ui.magazine import load_magazine_css, masthead
from ui.teacher_map import render_atlas

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead(
    "Reference",
    "Map atlas",
    "Full diagrams for contributors. Day-to-day orientation is the strip under each page masthead.",
)
render_atlas()
