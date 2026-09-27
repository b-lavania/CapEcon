"""
ADP compliance UI component for CapEcon.

This component provides reusable UI elements for ADP compliance visualization.
This is a NEW component - it does NOT replace any existing UI components.

Critical: This is ADDITIVE - all existing UI components remain unchanged.
"""

import streamlit as st
import pandas as pd


def render_adp_authorization_matrix(gdrs):
    """Render ADP authorization matrix visualization."""
    st.subheader("ADP Authorization Matrix")
    
    # Build authorization matrix
    autonomy_levels = ['A1', 'A2', 'A3', 'A4', 'A5']
    decision_types = ['operational', 'strategic', 'financial', 'regulatory']
    
    matrix_data = []
    for autonomy in autonomy_levels:
        for decision_type in decision_types:
            # Count GDRs with this combination
            count = 0
            approval_required = 0
            for gdr in gdrs:
                adp = gdr.get('adp', {})
                if adp.get('autonomy_level') == autonomy and adp.get('decision_type') == decision_type:
                    count += 1
                    if adp.get('authorization', {}).get('result') == 'approval_required':
                        approval_required += 1
            
            matrix_data.append({
                'Autonomy Level': autonomy,
                'Decision Type': decision_type,
                'Total GDRs': count,
                'Approval Required': approval_required,
                'Auto Approved': count - approval_required
            })
    
    df = pd.DataFrame(matrix_data)
    
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No ADP metadata available to display authorization matrix.")


def render_adp_risk_distribution(gdrs):
    """Render ADP risk level distribution."""
    st.subheader("Risk Level Distribution")
    
    risk_counts = {}
    for gdr in gdrs:
        adp = gdr.get('adp', {})
        risk = adp.get('risk_level', 'unknown')
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
    
    if risk_counts:
        st.bar_chart(risk_counts)
    else:
        st.info("No ADP metadata available to display risk distribution.")


def render_adp_autonomy_distribution(gdrs):
    """Render ADP autonomy level distribution."""
    st.subheader("Autonomy Level Distribution")
    
    autonomy_counts = {}
    for gdr in gdrs:
        adp = gdr.get('adp', {})
        autonomy = adp.get('autonomy_level', 'unknown')
        autonomy_counts[autonomy] = autonomy_counts.get(autonomy, 0) + 1
    
    if autonomy_counts:
        st.bar_chart(autonomy_counts)
    else:
        st.info("No ADP metadata available to display autonomy distribution.")


def render_adp_regulatory_overrides(gdrs):
    """Render GDRs where ADP overrode requires_review."""
    st.subheader("ADP Regulatory Overrides")
    
    overrides = []
    for gdr in gdrs:
        decision = gdr.get('decision', {})
        reason = decision.get('requires_review_reason', '')
        
        if 'ADP' in reason:
            overrides.append({
                'Record ID': gdr.get('record_id', 'unknown'),
                'Capability': gdr.get('subject', {}).get('capability_id', 'unknown'),
                'Override Reason': reason,
                'Autonomy Level': gdr.get('adp', {}).get('autonomy_level', 'N/A'),
                'Decision Type': gdr.get('adp', {}).get('decision_type', 'N/A')
            })
    
    if overrides:
        import pandas as pd
        df = pd.DataFrame(overrides)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No ADP regulatory overrides detected.")


def render_adp_validation_status(gdrs):
    """Render overall ADP validation status."""
    st.subheader("Validation Status")
    
    total = len(gdrs)
    validated = sum(1 for gdr in gdrs if gdr.get('adp'))
    failed = total - validated
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total GDRs", total)
    
    with col2:
        st.metric("Validated", validated)
    
    with col3:
        st.metric("Failed/No ADP", failed, delta_color="inverse")
    
    if validated > 0:
        st.success(f"{validated} GDRs successfully validated against ADP.")
    
    if failed > 0:
        st.warning(f"{failed} GDRs could not be validated or have no ADP metadata.")
