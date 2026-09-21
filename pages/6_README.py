"""Architecture reference — live atlas + docs mirrors."""

from pathlib import Path

import streamlit as st

from ui.magazine import load_magazine_css, masthead, section_kicker
from ui.teacher_map import render_atlas

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_magazine_css()
masthead(
    "Reference",
    "Architecture",
    "Join diagram and teacher clusters. Every agentic page also shows a slim orientation strip.",
)

section_kicker("Live atlas")
render_atlas()

arch = Path(__file__).parent.parent / "docs" / "architecture.md"
ia = Path(__file__).parent.parent / "docs" / "information_architecture.md"
if arch.exists() or ia.exists():
    section_kicker("Docs mirrors")
    if arch.exists():
        with st.expander("docs/architecture.md", expanded=False):
            st.markdown(arch.read_text())
    if ia.exists():
        with st.expander("docs/information_architecture.md", expanded=False):
            st.markdown(ia.read_text())

readme_path = Path(__file__).parent.parent / "README.md"
if readme_path.exists():
    with st.expander("Full README", expanded=False):
        st.markdown(readme_path.read_text())
