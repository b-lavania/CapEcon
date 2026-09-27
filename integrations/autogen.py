"""
AutoGen adapter for CapEcon.

This adapter intercepts AutoGen agent conversations and generates GDRs from conversation graphs.
This is a NEW adapter - it does NOT replace existing OTel/Langfuse adapters.

Critical: This is ADDITIVE - existing adapters remain unchanged.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime


class AutoGenAdapter:
    """
    Adapter for AutoGen agent conversations.
    
    Intercepts AutoGen agent conversations, extracts tool calls and outcomes,
    and generates GDRs from conversation graphs.
    
    This is a NEW adapter - does NOT replace existing OTel/Langfuse adapters.
    """
    
    def __init__(self):
        """Initialize AutoGen adapter."""
        self.version = "1.0.0"
    
    def ingest_autogen_conversation(self, conversation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Ingest an AutoGen conversation and generate GDRs.
        
        Args:
            conversation: AutoGen conversation dictionary containing message exchanges
        
        Returns:
            List of GrowthDecisionRecord dictionaries
        """
        gdrs = []
        
        # Extract message exchanges from conversation
        messages = conversation.get('messages', [])
        
        for message in messages:
            if message.get('role') == 'assistant':
                gdr = self._message_to_gdr(message, conversation)
                if gdr:
                    gdrs.append(gdr)
        
        return gdrs
    
    def _message_to_gdr(self, message: Dict[str, Any], conversation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert an AutoGen assistant message to a GDR.
        
        Args:
            message: AutoGen message dictionary
            conversation: Full AutoGen conversation for context
        
        Returns:
            GrowthDecisionRecord dictionary or None
        """
        # Extract key information
        message_id = message.get('message_id', '')
        agent_id = message.get('sender', '')
        conversation_id = conversation.get('conversation_id', '')
        
        # Build GDR structure
        gdr = {
            'record_id': f"autogen-{message_id}-{datetime.utcnow().isoformat()}",
            'vertical': 'orchestration',
            'schema_version': '2.0.0',
            'evaluated_at': datetime.utcnow().isoformat(),
            'evaluator_id': 'autogen_adapter',
            'subject': {
                'entity_type': 'capability',
                'capability_id': message.get('tool_name', 'general_assistant'),
                'agent_id': agent_id,
                'workspace_id': conversation_id
            },
            'exceptions': self._extract_exceptions(message),
            'decision': {
                'verdict': self._infer_verdict(message),
                'recommended_action': self._infer_action(message)
            },
            'economics': {
                'floor_usd': message.get('cost_usd', 0.0),
                'cap_usd': message.get('budget_cap', 0.0)
            },
            'evidence': {
                'claim_type': 'associational',
                'n': 1
            }
        }
        
        return gdr
    
    def _extract_exceptions(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract exceptions from AutoGen message.
        
        Args:
            message: AutoGen message dictionary
        
        Returns:
            List of exception dictionaries
        """
        exceptions = []
        
        # Check for errors
        if message.get('error'):
            exceptions.append({
                'exception_id': f"autogen-error-{message.get('message_id')}",
                'category': 'capability_dead',
                'description': message.get('error'),
                'severity': 'high',
                'owner_role': 'engineering'
            })
        
        # Check for tool call failures
        tool_calls = message.get('tool_calls', [])
        failed_calls = [tc for tc in tool_calls if tc.get('status') == 'failed']
        if failed_calls:
            exceptions.append({
                'exception_id': f"autogen-tool-{message.get('message_id')}",
                'category': 'handoff_failure',
                'description': f"{len(failed_calls)} tool calls failed",
                'severity': 'medium',
                'owner_role': 'engineering'
            })
        
        # Check for excessive message count (loop risk)
        message_count = message.get('conversation_message_count', 0)
        if message_count > 10:
            exceptions.append({
                'exception_id': f"autogen-loop-{message.get('message_id')}",
                'category': 'loop_exhaustion',
                'description': f"Conversation has {message_count} messages, possible loop",
                'severity': 'high',
                'owner_role': 'engineering'
            })
        
        return exceptions
    
    def _infer_verdict(self, message: Dict[str, Any]) -> str:
        """
        Infer verdict from AutoGen message.
        
        Args:
            message: AutoGen message dictionary
        
        Returns:
            Verdict string
        """
        if message.get('error'):
            return 'destructive'
        elif message.get('conversation_message_count', 0) > 10:
            return 'destructive'
        elif any(tc.get('status') == 'failed' for tc in message.get('tool_calls', [])):
            return 'leaking'
        else:
            return 'healthy'
    
    def _infer_action(self, message: Dict[str, Any]) -> str:
        """
        Infer recommended action from AutoGen message.
        
        Args:
            message: AutoGen message dictionary
        
        Returns:
            Recommended action string
        """
        if message.get('error'):
            return 'hold'
        elif message.get('conversation_message_count', 0) > 10:
            return 'kill'
        elif any(tc.get('status') == 'failed' for tc in message.get('tool_calls', [])):
            return 'revise'
        else:
            return 'ship'
    
    def emit_opentrajectory(self, conversation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Emit OpenTrajectory format from AutoGen conversation (OPTIONAL).
        
        Args:
            conversation: AutoGen conversation dictionary
        
        Returns:
            List of OpenTrajectory dictionaries
        """
        # Import OpenTrajectory exporter
        from standards.opentrajectory import OpenTrajectoryExporter
        
        exporter = OpenTrajectoryExporter()
        trajectories = []
        
        gdrs = self.ingest_autogen_conversation(conversation)
        for gdr in gdrs:
            trajectory = exporter.to_opentrajectory(gdr)
            trajectories.append(trajectory)
        
        return trajectories


# CRITICAL: This is a NEW adapter - does NOT replace existing OTel/Langfuse adapters
# Existing adapters (data/adapters/otel.py, data/adapters/langfuse.py) remain unchanged
