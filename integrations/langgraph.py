"""
LangGraph adapter for CapEcon.

This adapter intercepts LangGraph node execution and generates GDRs from LangGraph traces.
This is a NEW adapter - it does NOT replace existing OTel/Langfuse adapters.

Critical: This is ADDITIVE - existing adapters remain unchanged.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime


class LangGraphAdapter:
    """
    Adapter for LangGraph agent workflows.
    
    Intercepts LangGraph node execution, captures tool calls and outcomes,
    and generates GDRs from LangGraph traces.
    
    This is a NEW adapter - does NOT replace existing OTel/Langfuse adapters.
    """
    
    def __init__(self):
        """Initialize LangGraph adapter."""
        self.version = "1.0.0"
    
    def ingest_langgraph_trace(self, trace: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Ingest a LangGraph trace and generate GDRs.
        
        Args:
            trace: LangGraph trace dictionary containing node executions
        
        Returns:
            List of GrowthDecisionRecord dictionaries
        """
        gdrs = []
        
        # Extract node executions from trace
        node_executions = trace.get('node_executions', [])
        
        for node_execution in node_executions:
            gdr = self._node_execution_to_gdr(node_execution, trace)
            if gdr:
                gdrs.append(gdr)
        
        return gdrs
    
    def _node_execution_to_gdr(self, node_execution: Dict[str, Any], trace: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert a LangGraph node execution to a GDR.
        
        Args:
            node_execution: LangGraph node execution dictionary
            trace: Full LangGraph trace for context
        
        Returns:
            GrowthDecisionRecord dictionary or None
        """
        # Extract key information
        node_id = node_execution.get('node_id', '')
        node_name = node_execution.get('node_name', '')
        agent_id = node_execution.get('agent_id', '')
        
        # Build GDR structure
        gdr = {
            'record_id': f"langgraph-{node_id}-{datetime.utcnow().isoformat()}",
            'vertical': 'agent_runtime',
            'schema_version': '2.0.0',
            'evaluated_at': datetime.utcnow().isoformat(),
            'evaluator_id': 'langgraph_adapter',
            'subject': {
                'entity_type': 'capability',
                'capability_id': node_name,
                'agent_id': agent_id,
                'workspace_id': trace.get('workspace_id', '')
            },
            'exceptions': self._extract_exceptions(node_execution),
            'decision': {
                'verdict': self._infer_verdict(node_execution),
                'recommended_action': self._infer_action(node_execution)
            },
            'economics': {
                'floor_usd': node_execution.get('cost_usd', 0.0),
                'cap_usd': node_execution.get('budget_cap', 0.0)
            },
            'evidence': {
                'claim_type': 'associational',
                'n': 1
            }
        }
        
        return gdr
    
    def _extract_exceptions(self, node_execution: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract exceptions from LangGraph node execution.
        
        Args:
            node_execution: LangGraph node execution dictionary
        
        Returns:
            List of exception dictionaries
        """
        exceptions = []
        
        # Check for errors
        if node_execution.get('error'):
            exceptions.append({
                'exception_id': f"langgraph-error-{node_execution.get('node_id')}",
                'category': 'capability_dead',
                'description': node_execution.get('error'),
                'severity': 'high',
                'owner_role': 'engineering'
            })
        
        # Check for retries
        retry_count = node_execution.get('retry_count', 0)
        if retry_count > 3:
            exceptions.append({
                'exception_id': f"langgraph-retry-{node_execution.get('node_id')}",
                'category': 'activation_leak',
                'description': f"Node retried {retry_count} times",
                'severity': 'medium',
                'owner_role': 'engineering'
            })
        
        return exceptions
    
    def _infer_verdict(self, node_execution: Dict[str, Any]) -> str:
        """
        Infer verdict from LangGraph node execution.
        
        Args:
            node_execution: LangGraph node execution dictionary
        
        Returns:
            Verdict string
        """
        if node_execution.get('error'):
            return 'destructive'
        elif node_execution.get('retry_count', 0) > 3:
            return 'leaking'
        else:
            return 'healthy'
    
    def _infer_action(self, node_execution: Dict[str, Any]) -> str:
        """
        Infer recommended action from LangGraph node execution.
        
        Args:
            node_execution: LangGraph node execution dictionary
        
        Returns:
            Recommended action string
        """
        if node_execution.get('error'):
            return 'hold'
        elif node_execution.get('retry_count', 0) > 3:
            return 'revise'
        else:
            return 'ship'
    
    def emit_opentrajectory(self, trace: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Emit OpenTrajectory format from LangGraph trace (OPTIONAL).
        
        Args:
            trace: LangGraph trace dictionary
        
        Returns:
            List of OpenTrajectory dictionaries
        """
        # Import OpenTrajectory exporter
        from standards.opentrajectory import OpenTrajectoryExporter
        
        exporter = OpenTrajectoryExporter()
        trajectories = []
        
        gdrs = self.ingest_langgraph_trace(trace)
        for gdr in gdrs:
            trajectory = exporter.to_opentrajectory(gdr)
            trajectories.append(trajectory)
        
        return trajectories


# CRITICAL: This is a NEW adapter - does NOT replace existing OTel/Langfuse adapters
# Existing adapters (data/adapters/otel.py, data/adapters/langfuse.py) remain unchanged
