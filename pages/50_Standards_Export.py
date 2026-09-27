"""
Standards Export page for CapEcon.

This page allows users to export GDRs to standard formats (OpenDone, OpenTrajectory).
This is a NEW page - it does NOT replace any existing pages.

Critical: This is ADDITIVE - all existing pages remain unchanged.
"""

import streamlit as st
import json
from pathlib import Path

# Import standard exporters
try:
    from standards.opendone import OpenDoneExporter
    from standards.opentrajectory import OpenTrajectoryExporter
except ImportError:
    st.error("Standard exporters not available. Please ensure the standards package is installed.")
    st.stop()


def render_standards_export_page():
    """Render the Standards Export page."""
    
    st.title("Standards Export")
    st.markdown("""
    Export CapEcon GrowthDecisionRecords to external standard formats for interoperability.
    
    > **Note**: These are export formats only. CapEcon's internal proprietary formats remain the primary source of truth.
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
        st.info("No GDRs in workspace to export.")
        return
    
    st.subheader(f"Export {len(gdrs)} GDRs")
    
    # Export format selection
    col1, col2 = st.columns(2)
    
    with col1:
        export_format = st.selectbox(
            "Select export format",
            ["OpenTrajectory", "OpenDone"],
            help="OpenTrajectory: Vendor-neutral trajectory format (pure Python)\nOpenDone: Machine-verifiable outcome contracts (requires Node.js)"
        )
    
    with col2:
        export_all = st.checkbox("Export all GDRs", value=True)
    
    # GDR selection
    if not export_all:
        st.subheader("Select GDRs to export")
        gdr_options = {f"{gdr.get('record_id', 'unknown')} - {gdr.get('subject', {}).get('capability_id', 'unknown')}": gdr for gdr in gdrs}
        selected_gdrs = st.multiselect("Choose GDRs", list(gdr_options.keys()), default=list(gdr_options.keys())[:5])
        gdrs_to_export = [gdr_options[selection] for selection in selected_gdrs]
    else:
        gdrs_to_export = gdrs
    
    if not gdrs_to_export:
        st.warning("No GDRs selected for export.")
        return
    
    # Export button
    if st.button(f"Export to {export_format}", type="primary"):
        with st.spinner(f"Exporting to {export_format}..."):
            try:
                if export_format == "OpenTrajectory":
                    _export_opentrajectory(gdrs_to_export)
                elif export_format == "OpenDone":
                    _export_opendone(gdrs_to_export)
            except Exception as e:
                st.error(f"Export failed: {str(e)}")
                st.info("For OpenDone export, ensure Node.js and opendone are installed: `npm install -g opendone`")


def _export_opentrajectory(gdrs):
    """Export GDRs to OpenTrajectory format."""
    exporter = OpenTrajectoryExporter()
    
    trajectories = []
    for gdr in gdrs:
        trajectory = exporter.to_opentrajectory(gdr)
        trajectories.append(trajectory)
    
    # Display preview
    st.subheader("Export Preview")
    with st.expander("Show preview (first 3 trajectories)", expanded=False):
        for i, trajectory in enumerate(trajectories[:3]):
            st.json(trajectory)
    
    # Download button
    st.download_button(
        label="Download OpenTrajectory JSON",
        data=json.dumps(trajectories, indent=2),
        file_name="capEcon_opentrajectory_export.json",
        mime="application/json"
    )
    
    st.success(f"Successfully exported {len(trajectories)} GDRs to OpenTrajectory format.")


def _export_opendone(gdrs):
    """Export GDRs to OpenDone format."""
    try:
        exporter = OpenDoneExporter()
    except RuntimeError as e:
        st.error(str(e))
        st.info("See README.md for Node.js setup instructions.")
        return
    
    receipts = []
    for gdr in gdrs:
        try:
            receipt = exporter.to_opendone_receipt(gdr)
            receipts.append(receipt)
        except Exception as e:
            st.warning(f"Failed to export GDR {gdr.get('record_id', 'unknown')}: {str(e)}")
    
    if not receipts:
        st.error("No receipts generated.")
        return
    
    # Display preview
    st.subheader("Export Preview")
    with st.expander("Show preview (first 3 receipts)", expanded=False):
        for i, receipt in enumerate(receipts[:3]):
            st.json(receipt)
    
    # Download button
    st.download_button(
        label="Download OpenDone Receipts JSON",
        data=json.dumps(receipts, indent=2),
        file_name="capEcon_opendone_export.json",
        mime="application/json"
    )
    
    st.success(f"Successfully exported {len(receipts)} GDRs to OpenDone format.")


if __name__ == "__main__":
    render_standards_export_page()
