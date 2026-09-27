"""
CrewAI adapter for CapEcon.

This adapter hooks into CrewAI task execution and generates GDRs from crew traces.
This is a NEW adapter - it does NOT replace existing OTel/Langfuse adapters.

Critical: This is ADDITIVE - existing adapters remain unchanged.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime


class CrewAIAdapter:
    """
    Adapter for CrewAI agent workflows.
    
    Hooks into CrewAI task execution, captures crew and agent metadata,
    and generates GDRs from crew traces.
    
    This is a NEW adapter - does NOT replace existing OTel/Langfuse adapters.
    """
    
    def __init__(self):
        """Initialize CrewAI adapter."""
        self.version = "1.0.0"
    
    def ingest_crew_trace(self, trace: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Ingest a CrewAI trace and generate GDRs.
        
        Args:
            trace: CrewAI trace dictionary containing task executions
        
        Returns:
            List of GrowthDecisionRecord dictionaries
        """
        gdrs = []
        
        # Extract task executions from trace
        task_executions = trace.get('task_executions', [])
        
        for task_execution in task_executions:
            gdr = self._task_execution_to_gdr(task_execution, trace)
            if gdr:
                gdrs.append(gdr)
        
        return gdrs
    
    def _task_execution_to_gdr(self, task_execution: Dict[str, Any], trace: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert a CrewAI task execution to a GDR.
        
        Args:
            task_execution: CrewAI task execution dictionary
            trace: Full CrewAI trace for context
        
        Returns:
            GrowthDecisionRecord dictionary or None
        """
        # Extract key information
        task_id = task_execution.get('task_id', '')
        task_name = task_execution.get('task_name', '')
        agent_id = task_execution.get('agent_id', '')
        crew_id = trace.get('crew_id', '')
        
        # Build GDR structure
        gdr = {
            'record_id': f"crewai-{task_id}-{datetime.utcnow().isoformat()}",
            'vertical': 'orchestration',
            'schema_version': '2.0.0',
            'evaluated_at': datetime.utcnow().isoformat(),
            'evaluator_id': 'crewai_adapter',
            'subject': {
                'entity_type': 'capability',
                'capability_id': task_name,
                'agent_id': agent_id,
                'workspace_id': crew_id
            },
            'exceptions': self._extract_exceptions(task_execution),
            'decision': {
                'verdict': self._infer_verdict(task_execution),
                'recommended_action': self._infer_action(task_execution)
            },
            'economics': {
                'floor_usd': task_execution.get('cost_usd', 0.0),
                'cap_usd': task_execution.get('budget_cap', 0.0)
            },
            'evidence': {
                'claim_type': 'associational',
                'n': 1
            }
        }
        
        return gdr
    
    def _extract_exceptions(self, task_execution: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract exceptions from CrewAI task execution.
        
        Args:
            task_execution: CrewAI task execution dictionary
        
        Returns:
            List of exception dictionaries
        """
        exceptions = []
        
        # Check for errors
        if task_execution.get('error'):
            exceptions.append({
                'exception_id': f"crewai-error-{task_execution.get('task_id')}",
                'category': 'capability_dead',
                'description': task_execution.get('error'),
                'severity': 'high',
                'owner_role': 'engineering'
            })
        
        # Check for handoff failures
        if task_execution.get('handoff_failed'):
            exceptions.append({
                'exception_id': f"crewai-handoff-{task_execution.get('task_id')}",
                'category': 'handoff_failure',
                'description': 'Task handoff to next agent failed',
                'severity': 'medium',
                'owner_role': 'engineering'
            })
        
        # Check for coordination cost
        if task_execution.get('coordination_ratio', 0) > 0.35:
            exceptions.append({
                'exception_id': f"crewai-coord-{task_execution.get('task_id')}",
                'category': 'coordination_cost',
                'description': f"Coordination cost ratio {task_execution.get('coordination_ratio')} exceeds threshold",
                'severity': 'medium',
                'owner_role': 'data_science'
            })
        
        return exceptions
    
    def _infer_verdict(self, task_execution: Dict[str, Any]) -> str:
        """
        Infer verdict from CrewAI task execution.
        
        Args:
            task_execution: CrewAI task execution dictionary
        
        Returns:
            Verdict string
        """
        if task_execution.get('error'):
            return 'destructive'
        elif task_execution.get('handoff_failed'):
            return 'leaking'
        elif task_execution.get('coordination_ratio', 0) > 0.35:
            return 'uneconomic'
        else:
            return 'healthy'
    
    def _infer_action(self, task_execution: Dict[str, Any]) -> str:
        """
        Infer recommended action from CrewAI task execution.
        
        Args:
            task_execution: CrewAI task execution dictionary
        
        Returns:
            Recommended action string
        """
        if task_execution.get('error'):
            return 'hold'
        elif task_execution.get('handoff_failed'):
            return 'experiment'
        elif task_execution.get('coordination_ratio', 0) > 0.35:
            return 'throttle'
        else:
            return 'ship'
    
    def emit_opentrajectory(self, trace: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Emit OpenTrajectory format from CrewAI trace (OPTIONAL).
        
        Args:
            trace: CrewAI trace dictionary
        
        Returns:
            List of OpenTrajectory dictionaries
        """
        # Import OpenTrajectory exporter
        from standards.opentrajectory import OpenTrajectoryExporter
        
        exporter = OpenTrajectoryExporter()
        trajectories = []
        
        gdrs = self.ingest_crew_trace(trace)
        for gdr in gdrs:
            trajectory = exporter.to_opentrajectory(gdr)
            trajectories.append(trajectory)
        
        return trajectories


# CRITICAL: This is a NEW adapter - does NOT replace existing OTel/Langfuse adapters
# Existing adapters (data/adapters/otel.py, data/adapters/langfuse.py) remain unchanged
