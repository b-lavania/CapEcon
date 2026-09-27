"""
Generic OpenTelemetry bridge for CapEcon.

This adapter ingests OTel GenAI spans and generates GDRs from spans.
This is a NEW adapter - it does NOT replace the existing data/adapters/otel.py.

Critical: This is ADDITIVE - existing adapters remain unchanged.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime


class OTelAdapter:
    """
    Generic OpenTelemetry bridge for any OTel-instrumented agent.
    
    Ingests OTel GenAI spans, converts to OpenTrajectory format (OPTIONAL),
    and generates GDRs from spans.
    
    This is a NEW adapter - does NOT replace existing data/adapters/otel.py.
    """
    
    def __init__(self):
        """Initialize OTel adapter."""
        self.version = "1.0.0"
    
    def ingest_otel_spans(self, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ingest OTel GenAI spans and generate GDRs.
        
        Args:
            spans: List of OTel span dictionaries
        
        Returns:
            List of GrowthDecisionRecord dictionaries
        """
        gdrs = []
        
        for span in spans:
            # Only process GenAI spans
            if self._is_genai_span(span):
                gdr = self._span_to_gdr(span)
                if gdr:
                    gdrs.append(gdr)
        
        return gdrs
    
    def _is_genai_span(self, span: Dict[str, Any]) -> bool:
        """
        Check if span is a GenAI span.
        
        Args:
            span: OTel span dictionary
        
        Returns:
            True if GenAI span, False otherwise
        """
        attributes = span.get('attributes', {})
        
        # Check for GenAI semantic conventions
        genai_keys = [
            'gen_ai.system',
            'gen_ai.request.model',
            'gen_ai.response.model',
            'gen_ai.type'
        ]
        
        return any(key in attributes for key in genai_keys)
    
    def _span_to_gdr(self, span: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert an OTel span to a GDR.
        
        Args:
            span: OTel span dictionary
        
        Returns:
            GrowthDecisionRecord dictionary or None
        """
        attributes = span.get('attributes', {})
        
        # Extract key information
        span_id = span.get('span_id', '')
        trace_id = span.get('trace_id', '')
        agent_id = attributes.get('gen_ai.system', 'unknown')
        model = attributes.get('gen_ai.request.model', 'unknown')
        
        # Build GDR structure
        gdr = {
            'record_id': f"otel-{span_id}",
            'vertical': 'agent_runtime',
            'schema_version': '2.0.0',
            'evaluated_at': datetime.utcnow().isoformat(),
            'evaluator_id': 'otel_adapter',
            'subject': {
                'entity_type': 'capability',
                'capability_id': model,
                'agent_id': agent_id,
                'workspace_id': trace_id
            },
            'exceptions': self._extract_exceptions(span),
            'decision': {
                'verdict': self._infer_verdict(span),
                'recommended_action': self._infer_action(span)
            },
            'economics': {
                'floor_usd': self._extract_cost(span),
                'cap_usd': 0.0  # Cap not available from OTel spans
            },
            'evidence': {
                'claim_type': 'associational',
                'n': 1
            }
        }
        
        return gdr
    
    def _extract_exceptions(self, span: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract exceptions from OTel span.
        
        Args:
            span: OTel span dictionary
        
        Returns:
            List of exception dictionaries
        """
        exceptions = []
        
        # Check for span status error
        status = span.get('status', {})
        if status.get('code') == 'ERROR':
            exceptions.append({
                'exception_id': f"otel-error-{span.get('span_id')}",
                'category': 'capability_dead',
                'description': status.get('description', 'Span status error'),
                'severity': 'high',
                'owner_role': 'engineering'
            })
        
        # Check for high latency
        duration_ms = span.get('end_time_nanos', 0) - span.get('start_time_nanos', 0)
        duration_seconds = duration_ms / 1_000_000_000
        if duration_seconds > 30:
            exceptions.append({
                'exception_id': f"otel-latency-{span.get('span_id')}",
                'category': 'run_cost_blowout',
                'description': f"Span duration {duration_seconds:.2f}s exceeds threshold",
                'severity': 'medium',
                'owner_role': 'engineering'
            })
        
        # Check for high token count
        attributes = span.get('attributes', {})
        total_tokens = attributes.get('gen_ai.usage.total_tokens', 0)
        if total_tokens > 10000:
            exceptions.append({
                'exception_id': f"otel-tokens-{span.get('span_id')}",
                'category': 'run_cost_blowout',
                'description': f"Token count {total_tokens} exceeds threshold",
                'severity': 'medium',
                'owner_role': 'data_science'
            })
        
        return exceptions
    
    def _extract_cost(self, span: Dict[str, Any]) -> float:
        """
        Extract cost from OTel span.
        
        Args:
            span: OTel span dictionary
        
        Returns:
            Cost in USD
        """
        attributes = span.get('attributes', {})
        
        # Try to get cost from attributes
        cost = attributes.get('gen_ai.cost', 0.0)
        if cost:
            return float(cost)
        
        # Estimate from token count if cost not available
        total_tokens = attributes.get('gen_ai.usage.total_tokens', 0)
        model = attributes.get('gen_ai.request.model', '')
        
        # Simple cost estimation (placeholder)
        if 'gpt-4' in model.lower():
            return total_tokens * 0.00003  # $0.03 per 1K tokens
        elif 'gpt-3.5' in model.lower():
            return total_tokens * 0.000002  # $0.002 per 1K tokens
        else:
            return total_tokens * 0.00001  # Default $0.01 per 1K tokens
    
    def _infer_verdict(self, span: Dict[str, Any]) -> str:
        """
        Infer verdict from OTel span.
        
        Args:
            span: OTel span dictionary
        
        Returns:
            Verdict string
        """
        status = span.get('status', {})
        if status.get('code') == 'ERROR':
            return 'destructive'
        
        exceptions = self._extract_exceptions(span)
        if any(exc['category'] == 'run_cost_blowout' for exc in exceptions):
            return 'uneconomic'
        
        return 'healthy'
    
    def _infer_action(self, span: Dict[str, Any]) -> str:
        """
        Infer recommended action from OTel span.
        
        Args:
            span: OTel span dictionary
        
        Returns:
            Recommended action string
        """
        status = span.get('status', {})
        if status.get('code') == 'ERROR':
            return 'hold'
        
        exceptions = self._extract_exceptions(span)
        if any(exc['category'] == 'run_cost_blowout' for exc in exceptions):
            return 'throttle'
        
        return 'ship'
    
    def emit_opentrajectory(self, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Emit OpenTrajectory format from OTel spans (OPTIONAL).
        
        Args:
            spans: List of OTel span dictionaries
        
        Returns:
            List of OpenTrajectory dictionaries
        """
        # Import OpenTrajectory exporter
        from standards.opentrajectory import OpenTrajectoryExporter
        
        exporter = OpenTrajectoryExporter()
        trajectories = []
        
        gdrs = self.ingest_otel_spans(spans)
        for gdr in gdrs:
            trajectory = exporter.to_opentrajectory(gdr)
            trajectories.append(trajectory)
        
        return trajectories


# CRITICAL: This is a NEW adapter - does NOT replace existing data/adapters/otel.py
# Existing adapters (data/adapters/otel.py, data/adapters/langfuse.py) remain unchanged
