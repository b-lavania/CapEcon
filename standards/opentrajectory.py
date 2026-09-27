"""
OpenTrajectory exporter for CapEcon.

This module exports CapEcon GrowthDecisionRecords to OpenTrajectory format.
OpenTrajectory is an optional export format - CapEcon's internal classification and verdict system remains the primary format.

This is a pure Python implementation with no JavaScript dependencies.

Critical: This is an EXPORT layer, not a replacement for CapEcon's internal classification.
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime


class OpenTrajectoryExporter:
    """
    Export CapEcon GDR to OpenTrajectory format (pure Python).
    
    OpenTrajectory is a vendor-neutral format for AI agent trajectories.
    This exporter maps CapEcon's richer GDR structure to the OpenTrajectory format.
    
    This is a pure Python implementation with no external dependencies.
    """
    
    def __init__(self, version: str = "0.1"):
        """
        Initialize OpenTrajectory exporter.
        
        Args:
            version: OpenTrajectory format version (default: "0.1")
        """
        self.version = version
    
    def to_opentrajectory(self, gdr: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export GDR to OpenTrajectory format.
        
        Maps CapEcon's richer GDR structure to OpenTrajectory's trajectory format.
        This is an EXPORT - CapEcon's internal classification and verdict system remains primary.
        
        Args:
            gdr: CapEcon GrowthDecisionRecord dictionary
        
        Returns:
            OpenTrajectory dictionary
        """
        trajectory = {
            'version': self.version,
            'run_id': gdr.get('record_id', ''),
            'agent_id': gdr.get('subject', {}).get('agent_id', ''),
            'steps': self._map_exceptions_to_steps(gdr.get('exceptions', [])),
            'tool_calls': self._extract_tool_calls(gdr),
            'outcome': {
                'success': gdr.get('decision', {}).get('verdict') == 'healthy',
                'verified': gdr.get('outcome', {}).get('verified_by') is not None
            },
            'verdict': {
                'classification': self._map_verdict_to_ot_verdict(gdr.get('decision', {}).get('verdict')),
                'confidence': gdr.get('evidence', {}).get('confidence', 0.0)
            }
        }
        
        return trajectory
    
    def _map_exceptions_to_steps(self, exceptions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Map CapEcon exceptions to OpenTrajectory steps.
        
        CapEcon has a rich exception taxonomy (15+ categories).
        OpenTrajectory has a simpler step structure. This is a lossy mapping for export.
        
        Args:
            exceptions: List of CapEcon exception dictionaries
        
        Returns:
            List of OpenTrajectory step dictionaries
        """
        steps = []
        
        for exc in exceptions:
            step = {
                'step_id': exc.get('exception_id', ''),
                'step_type': exc.get('category', 'unknown'),
                'description': exc.get('description', ''),
                'timestamp': exc.get('timestamp', datetime.utcnow().isoformat()),
                'severity': exc.get('severity', 'medium'),
                'metadata': {
                    'owner_role': exc.get('owner_role', ''),
                    'playbook_hint': exc.get('playbook_hint', '')
                }
            }
            steps.append(step)
        
        return steps
    
    def _extract_tool_calls(self, gdr: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract tool calls from GDR.
        
        OpenTrajectory expects a list of tool calls. CapEcon's GDR may have tool call
        information in different locations depending on the adapter used.
        
        Args:
            gdr: CapEcon GrowthDecisionRecord dictionary
        
        Returns:
            List of tool call dictionaries
        """
        tool_calls = []
        
        # Try to extract tool calls from the GDR structure
        # This is a placeholder - actual implementation depends on GDR structure
        subject = gdr.get('subject', {})
        if 'tool_calls' in subject:
            tool_calls = subject['tool_calls']
        
        return tool_calls
    
    def _map_verdict_to_ot_verdict(self, verdict: Optional[str]) -> str:
        """
        Map CapEcon verdict to OpenTrajectory verdict classification.
        
        CapEcon verdicts: healthy, leaking, destructive, uneconomic, underpowered, needs_review
        OpenTrajectory verdicts: success, failure, unknown
        
        Args:
            verdict: CapEcon verdict string
        
        Returns:
            OpenTrajectory verdict classification
        """
        verdict_map = {
            'healthy': 'success',
            'leaking': 'failure',
            'destructive': 'failure',
            'uneconomic': 'failure',
            'underpowered': 'failure',
            'needs_review': 'unknown'
        }
        
        return verdict_map.get(verdict, 'unknown')
    
    def export_batch(self, gdrs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Export multiple GDRs to OpenTrajectory format.
        
        Args:
            gdrs: List of CapEcon GrowthDecisionRecord dictionaries
        
        Returns:
            List of OpenTrajectory dictionaries
        """
        trajectories = []
        for gdr in gdrs:
            trajectory = self.to_opentrajectory(gdr)
            trajectories.append(trajectory)
        return trajectories
    
    def save_to_file(self, trajectory: Dict[str, Any], output_path: str):
        """
        Save OpenTrajectory to a .ot.json file.
        
        Args:
            trajectory: OpenTrajectory dictionary
            output_path: Path to save the file
        """
        with open(output_path, 'w') as f:
            json.dump(trajectory, f, indent=2)
    
    def save_batch_to_files(self, trajectories: List[Dict[str, Any]], output_dir: str):
        """
        Save multiple OpenTrajectory files to a directory.
        
        Args:
            trajectories: List of OpenTrajectory dictionaries
            output_dir: Directory to save files
        """
        from pathlib import Path
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for trajectory in trajectories:
            run_id = trajectory.get('run_id', 'unknown')
            file_path = output_path / f"{run_id}.ot.json"
            self.save_to_file(trajectory, str(file_path))


# CRITICAL: OpenTrajectory is an EXPORT format, not the primary format
# CapEcon's internal classification and verdict system remains unchanged
# Existing OTel/Langfuse adapters remain unchanged
