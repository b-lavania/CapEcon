"""
Standards export UI component for CapEcon.

This component provides reusable UI elements for standards export functionality.
This is a NEW component - it does NOT replace any existing UI components.

Critical: This is ADDITIVE - all existing UI components remain unchanged.
"""

import streamlit as st
import json


def render_export_format_selector():
    """Render export format selection UI."""
    col1, col2 = st.columns(2)
    
    with col1:
        export_format = st.selectbox(
            "Export format",
            ["OpenTrajectory", "OpenDone"],
            key="export_format_selector",
            help="OpenTrajectory: Vendor-neutral trajectory format\nOpenDone: Machine-verifiable outcome contracts"
        )
    
    with col2:
        export_all = st.checkbox("Export all records", value=True, key="export_all_selector")
    
    return export_format, export_all


def render_export_preview(data, max_preview=3):
    """Render export preview with expandable section."""
    st.subheader("Export Preview")
    
    if not data:
        st.info("No data to preview.")
        return
    
    with st.expander(f"Show preview (first {max_preview} items)", expanded=False):
        for i, item in enumerate(data[:max_preview]):
            st.write(f"**Item {i+1}**")
            st.json(item)
            st.divider()
        
        if len(data) > max_preview:
            st.info(f"... and {len(data) - max_preview} more items")


def render_download_button(data, filename, label="Download JSON"):
    """Render download button for JSON data."""
    if not data:
        st.warning("No data to download.")
        return
    
    st.download_button(
        label=label,
        data=json.dumps(data, indent=2),
        file_name=filename,
        mime="application/json"
    )


def render_adp_summary_table(adp_data):
    """Render ADP compliance summary table."""
    import pandas as pd
    
    df = pd.DataFrame(adp_data)
    
    def highlight_authorization(row):
        if row['Authorization'] == 'approval_required':
            return ['background-color: #ffcccc'] * len(row)
        elif row['Authorization'] == 'auto_approved':
            return ['background-color: #ccffcc'] * len(row)
        else:
            return [''] * len(row)
    
    st.dataframe(
        df.style.apply(highlight_authorization, axis=1),
        use_container_width=True,
        hide_index=True
    )


def render_compliance_metrics(adp_data):
    """Render compliance metrics as metric cards."""
    import pandas as pd
    
    df = pd.DataFrame(adp_data)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        approval_required = len(df[df['Authorization'] == 'approval_required'])
        st.metric("Approval Required", approval_required)
    
    with col2:
        auto_approved = len(df[df['Authorization'] == 'auto_approved'])
        st.metric("Auto Approved", auto_approved)
    
    with col3:
        high_risk = len(df[df['Risk Level'] == 'high'])
        st.metric("High Risk", high_risk)
    
    with col4:
        critical_risk = len(df[df['Risk Level'] == 'critical'])
        st.metric("Critical Risk", critical_risk)


def render_policy_card_sections(policy_card):
    """Render Policy Card sections in a grid layout."""
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Policy ID**")
        st.code(policy_card.get('policy_id', 'N/A'))
        
        st.write("**Name**")
        st.code(policy_card.get('name', 'N/A'))
    
    with col2:
        st.write("**Category**")
        st.code(policy_card.get('category', 'N/A'))
        
        rules_count = len(policy_card.get('rules', []))
        st.write(f"**Rules Count**: {rules_count}")
