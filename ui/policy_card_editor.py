"""
Policy Card editor UI component for CapEcon.

This component provides reusable UI elements for Policy Card editing and validation.
This is a NEW component - it does NOT replace any existing UI components.

Critical: This is ADDITIVE - all existing UI components remain unchanged.
"""

import streamlit as st
import json


def render_policy_card_editor(policy_card):
    """Render Policy Card editor interface."""
    st.subheader("Policy Card Editor")
    
    # Editable fields
    with st.form("policy_card_form"):
        st.write("**Policy ID**")
        policy_id = st.text_input("Policy ID", value=policy_card.get('policy_id', ''), key="pc_policy_id")
        
        st.write("**Name**")
        name = st.text_input("Name", value=policy_card.get('name', ''), key="pc_name")
        
        st.write("**Category**")
        category = st.selectbox(
            "Category",
            ["operational", "governance", "technical", "compliance"],
            index=["operational", "governance", "technical", "compliance"].index(policy_card.get('category', 'operational')),
            key="pc_category"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Update Policy Card", type="primary")
        with col2:
            reset = st.form_submit_button("Reset to Original")
        
        if submitted:
            policy_card['policy_id'] = policy_id
            policy_card['name'] = name
            policy_card['category'] = category
            st.success("Policy Card updated.")
            return policy_card
        
        if reset:
            st.info("Reset to original values.")
            return policy_card
    
    return policy_card


def render_regulatory_crosswalk_editor(regulatory_mapping):
    """Render regulatory crosswalk editor."""
    st.subheader("Regulatory Crosswalk")
    
    # EU AI Act
    with st.expander("EU AI Act", expanded=False):
        eu_act = regulatory_mapping.get('eu_ai_act', {})
        
        category = st.selectbox(
            "Category",
            ["prohibited", "high_risk", "limited_risk", "minimal_risk"],
            index=["prohibited", "high_risk", "limited_risk", "minimal_risk"].index(eu_act.get('category', 'limited_risk')),
            key="eu_act_category"
        )
        
        risk_level = st.selectbox(
            "Risk Level",
            ["unacceptable", "high", "limited", "minimal"],
            index=["unacceptable", "high", "limited", "minimal"].index(eu_act.get('risk_level', 'limited')),
            key="eu_act_risk"
        )
        
        if st.button("Update EU AI Act", key="update_eu_act"):
            regulatory_mapping['eu_ai_act'] = {'category': category, 'risk_level': risk_level}
            st.success("EU AI Act mapping updated.")
    
    # NIST AI RMF
    with st.expander("NIST AI RMF", expanded=False):
        nist = regulatory_mapping.get('nist_ai_rmf', {})
        
        category = st.text_input("Category", value=nist.get('category', 'govern'), key="nist_category")
        
        functions = st.multiselect(
            "Functions",
            ["govern", "map", "measure", "manage"],
            default=nist.get('functions', []),
            key="nist_functions"
        )
        
        if st.button("Update NIST AI RMF", key="update_nist"):
            regulatory_mapping['nist_ai_rmf'] = {'category': category, 'functions': functions}
            st.success("NIST AI RMF mapping updated.")
    
    # ISO 42001
    with st.expander("ISO 42001", expanded=False):
        iso = regulatory_mapping.get('iso_42001', {})
        
        category = st.text_input("Category", value=iso.get('category', 'aims'), key="iso_category")
        
        controls = st.text_area(
            "Controls (comma-separated)",
            value=', '.join(iso.get('controls', [])),
            key="iso_controls"
        )
        
        if st.button("Update ISO 42001", key="update_iso"):
            controls_list = [c.strip() for c in controls.split(',') if c.strip()]
            regulatory_mapping['iso_42001'] = {'category': category, 'controls': controls_list}
            st.success("ISO 42001 mapping updated.")
    
    return regulatory_mapping


def render_evidence_requirements_editor(evidence_requirements):
    """Render evidence requirements editor."""
    st.subheader("Evidence Requirements")
    
    min_verified_share = st.slider(
        "Minimum Verified Share",
        min_value=0.0,
        max_value=1.0,
        value=evidence_requirements.get('min_verified_share', 0.40),
        step=0.05,
        key="min_verified_share"
    )
    
    requires_experiment_id = st.checkbox(
        "Requires Experiment ID",
        value=evidence_requirements.get('requires_experiment_id', False),
        key="requires_experiment_id"
    )
    
    evidence_types = st.multiselect(
        "Allowed Evidence Types",
        ["simulated", "associational", "causal"],
        default=evidence_requirements.get('evidence_types', []),
        key="evidence_types"
    )
    
    if st.button("Update Evidence Requirements", key="update_evidence"):
        evidence_requirements['min_verified_share'] = min_verified_share
        evidence_requirements['requires_experiment_id'] = requires_experiment_id
        evidence_requirements['evidence_types'] = evidence_types
        st.success("Evidence requirements updated.")
    
    return evidence_requirements


def render_policy_card_validation(policy_card):
    """Render Policy Card validation status."""
    st.subheader("Validation Status")
    
    try:
        from standards.policy_cards import PolicyCardExporter
        exporter = PolicyCardExporter()
        
        # Validate against local schema
        exporter._validate_policy_card(policy_card)
        
        st.success("✅ Policy Card is valid against local schema.")
        
        # Display schema info
        st.info(f"Schema: {policy_card.get('$schema', 'N/A')}")
        
    except Exception as e:
        st.error(f"❌ Validation failed: {str(e)}")


def render_policy_card_diff(original, modified):
    """Render diff between original and modified Policy Card."""
    st.subheader("Policy Card Diff")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Original**")
        st.json(original)
    
    with col2:
        st.write("**Modified**")
        st.json(modified)
    
    # Highlight changes
    changes = []
    for key in set(list(original.keys()) + list(modified.keys())):
        if original.get(key) != modified.get(key):
            changes.append({
                'Field': key,
                'Original': original.get(key, 'N/A'),
                'Modified': modified.get(key, 'N/A')
            })
    
    if changes:
        st.write("**Changes**")
        import pandas as pd
        df = pd.DataFrame(changes)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No changes detected.")
