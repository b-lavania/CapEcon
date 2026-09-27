"""
Policy Card Editor page for CapEcon.

This page exports CapEcon YAML semantics to Policy Card format.
This is a NEW page - it does NOT replace any existing pages.

Critical: This is ADDITIVE - all existing pages remain unchanged.
Policy Cards is an export format only, not a replacement for CapEcon's YAML semantics.
"""

import streamlit as st
import json
from pathlib import Path

# Import Policy Card exporter
try:
    from standards.policy_cards import PolicyCardExporter
except ImportError:
    st.error("Policy Card exporter not available. Please ensure the standards package is installed.")
    st.stop()


def render_policy_card_editor_page():
    """Render the Policy Card Editor page."""
    
    st.title("Policy Card Editor")
    st.markdown("""
    Export CapEcon YAML semantics to Policy Card format for external policy management.
    
    > **Note**: Policy Cards is an export format only. CapEcon's YAML semantics with verdict/action maps remains the primary format.
    """)
    
    # Select vertical
    vertical = st.selectbox(
        "Select vertical to export",
        ["agent_runtime", "capability_lifecycle", "clinical_runtime", "eval_governance", "marketplace_commerce", "orchestration"],
        help="Choose the vertical whose semantics.yaml you want to export"
    )
    
    # Build path to semantics.yaml
    semantics_path = Path(__file__).parent.parent / "ontology" / vertical / "semantics.yaml"
    
    if not semantics_path.exists():
        st.error(f"Semantics file not found: {semantics_path}")
        return
    
    # Export button
    if st.button("Export to Policy Card", type="primary"):
        with st.spinner(f"Exporting {vertical} semantics to Policy Card..."):
            try:
                exporter = PolicyCardExporter()
                policy_card = exporter.to_policy_card(str(semantics_path))
                
                _display_policy_card(policy_card, vertical)
                
            except Exception as e:
                st.error(f"Export failed: {str(e)}")


def _display_policy_card(policy_card, vertical):
    """Display Policy Card export."""
    st.subheader(f"Policy Card Export: {vertical}")
    
    # Display Policy Card JSON
    with st.expander("View Policy Card JSON", expanded=True):
        st.json(policy_card)
    
    # Display key sections
    st.subheader("Policy Card Sections")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Policy ID**")
        st.code(policy_card.get('policy_id', 'N/A'))
        
        st.write("**Name**")
        st.code(policy_card.get('name', 'N/A'))
        
        st.write("**Category**")
        st.code(policy_card.get('category', 'N/A'))
    
    with col2:
        st.write("**Schema**")
        st.code(policy_card.get('$schema', 'N/A'))
        
        # Check if policy_card_export is enabled in semantics
        rules_count = len(policy_card.get('rules', []))
        st.write(f"**Rules Count**: {rules_count}")
    
    # Display rules
    if policy_card.get('rules'):
        st.subheader("Rules")
        for i, rule in enumerate(policy_card['rules'][:5]):  # Show first 5 rules
            with st.expander(f"Rule {i+1}: {rule.get('rule_id', 'unknown')}", expanded=False):
                st.json(rule)
        
        if len(policy_card['rules']) > 5:
            st.info(f"... and {len(policy_card['rules']) - 5} more rules")
    
    # Display regulatory mapping
    if policy_card.get('regulatory_mapping'):
        st.subheader("Regulatory Mapping")
        regulatory = policy_card['regulatory_mapping']
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**EU AI Act**")
            eu_act = regulatory.get('eu_ai_act', {})
            st.json(eu_act)
        
        with col2:
            st.write("**NIST AI RMF**")
            nist = regulatory.get('nist_ai_rmf', {})
            st.json(nist)
        
        with col3:
            st.write("**ISO 42001**")
            iso = regulatory.get('iso_42001', {})
            st.json(iso)
    
    # Display evidence requirements
    if policy_card.get('evidence_requirements'):
        st.subheader("Evidence Requirements")
        st.json(policy_card['evidence_requirements'])
    
    # Download button
    st.download_button(
        label=f"Download {vertical} Policy Card JSON",
        data=json.dumps(policy_card, indent=2),
        file_name=f"capEcon_{vertical}_policy_card.json",
        mime="application/json"
    )
    
    # Validation status
    st.success(f"Successfully exported {vertical} semantics to Policy Card format.")
    st.info("Policy Card validated against local schema. To update schema from external URL, use the Policy Card exporter in Python code.")


if __name__ == "__main__":
    render_policy_card_editor_page()
