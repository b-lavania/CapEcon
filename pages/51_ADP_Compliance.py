"""
ADP Compliance page for CapEcon.

This page displays ADP compliance status and authorization matrix.
This is a NEW page - it does NOT replace any existing pages.

Critical: This is ADDITIVE - all existing pages remain unchanged.
ADP is an OPTIONAL validation layer, not a replacement for CapEcon's triage system.
"""

import streamlit as st
import json
import pandas as pd

# Import ADP validator
try:
    from standards.adp import ADPValidator
except ImportError:
    st.error("ADP validator not available. Please ensure the standards package is installed.")
    st.stop()


def render_adp_compliance_page():
    """Render the ADP Compliance page."""
    
    st.title("ADP Compliance")
    st.markdown("""
    View ADP (Agent Decision Protocol) compliance status and authorization matrix.
    
    > **Note**: ADP is an OPTIONAL validation layer for regulatory compliance. 
    > CapEcon's triage system (TRIAGE_STATES, ROLE_OWNERS) remains the primary triage mechanism.
    """)
    
    # Check if workspace exists
    if 'workspace' not in st.session_state or not st.session_state.workspace:
        st.warning("No workspace loaded. Please generate a workspace first.")
        st.page_link("pages/00_Agentic_Product_Profile.py", label="Go to Product Profile", icon="🔙")
        return
    
    # Get GDRs from workspace
    workspace = st.session_state.workspace
    gdrs = workspace.get('gdrs', [])
    
    if not gdrs:
        st.info("No GDRs in workspace to validate.")
        return
    
    st.subheader(f"Validate {len(gdrs)} GDRs against ADP")
    
    # ADP validation button
    col1, col2 = st.columns([1, 3])
    
    with col1:
        validate_all = st.button("Validate All GDRs", type="primary")
    
    with col2:
        st.info("For ADP validation, ensure Node.js and @adp/core are installed: `npm install -g @adp/core`")
    
    if validate_all:
        with st.spinner("Validating GDRs against ADP..."):
            try:
                validator = ADPValidator()
            except RuntimeError as e:
                st.error(str(e))
                st.info("See README.md for Node.js setup instructions.")
                return
            
            validated_gdrs = []
            errors = []
            
            for gdr in gdrs:
                try:
                    validated_gdr = validator.add_adp_metadata(gdr.copy())
                    validated_gdrs.append(validated_gdr)
                except Exception as e:
                    errors.append(f"GDR {gdr.get('record_id', 'unknown')}: {str(e)}")
            
            if errors:
                st.warning(f"Failed to validate {len(errors)} GDRs:")
                for error in errors:
                    st.text(error)
            
            if validated_gdrs:
                _display_adp_compliance_results(validated_gdrs)


def _display_adp_compliance_results(gdrs):
    """Display ADP compliance results."""
    st.subheader("ADP Compliance Results")
    
    # Extract ADP metadata
    adp_data = []
    for gdr in gdrs:
        adp = gdr.get('adp', {})
        adp_data.append({
            'Record ID': gdr.get('record_id', 'unknown'),
            'Capability': gdr.get('subject', {}).get('capability_id', 'unknown'),
            'Autonomy Level': adp.get('autonomy_level', 'N/A'),
            'Decision Type': adp.get('decision_type', 'N/A'),
            'Risk Level': adp.get('risk_level', 'N/A'),
            'Classification': adp.get('classification_code', 'N/A'),
            'Authorization': adp.get('authorization', {}).get('result', 'N/A'),
            'Original Verdict': gdr.get('decision', {}).get('verdict', 'N/A'),
            'Requires Review': gdr.get('decision', {}).get('requires_review', False)
        })
    
    # Display as table
    df = pd.DataFrame(adp_data)
    
    # Color code authorization results
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
    
    # Summary statistics
    st.subheader("Summary")
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
    
    # Autonomy level distribution
    st.subheader("Autonomy Level Distribution")
    autonomy_counts = df['Autonomy Level'].value_counts()
    st.bar_chart(autonomy_counts)
    
    # Decision type distribution
    st.subheader("Decision Type Distribution")
    decision_counts = df['Decision Type'].value_counts()
    st.bar_chart(decision_counts)
    
    # Download button
    st.download_button(
        label="Download ADP Compliance Report JSON",
        data=json.dumps(adp_data, indent=2),
        file_name="capEcon_adp_compliance_report.json",
        mime="application/json"
    )
    
    st.success(f"Successfully validated {len(gdrs)} GDRs against ADP.")


if __name__ == "__main__":
    render_adp_compliance_page()
