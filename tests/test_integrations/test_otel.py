"""
Mocked unit tests for OTel adapter.

These tests use mocks to validate the adapter logic without requiring actual OTel installations.
"""

import pytest
from unittest.mock import Mock, patch

try:
    from integrations.otel import OTelAdapter
except ImportError:
    pytest.skip("OTel adapter not yet implemented", allow_module_level=True)


class TestOTelAdapter:
    """Test OTel adapter with mocked spans."""
    
    def test_init(self):
        """Test successful initialization."""
        adapter = OTelAdapter()
        assert adapter.version == "1.0.0"
    
    def test_ingest_otel_spans(self):
        """Test ingesting OTel spans."""
        adapter = OTelAdapter()
        
        spans = [
            {
                'span_id': 'span-001',
                'trace_id': 'trace-001',
                'attributes': {
                    'gen_ai.system': 'openai',
                    'gen_ai.request.model': 'gpt-4',
                    'gen_ai.usage.total_tokens': 1000
                }
            }
        ]
        
        gdrs = adapter.ingest_otel_spans(spans)
        
        assert len(gdrs) == 1
        assert gdrs[0]['subject']['capability_id'] == 'gpt-4'
        assert gdrs[0]['subject']['agent_id'] == 'openai'
        assert gdrs[0]['vertical'] == 'agent_runtime'
    
    def test_is_genai_span(self):
        """Test checking if span is GenAI span."""
        adapter = OTelAdapter()
        
        # GenAI span
        genai_span = {
            'attributes': {'gen_ai.system': 'openai'}
        }
        assert adapter._is_genai_span(genai_span) is True
        
        # Non-GenAI span
        regular_span = {
            'attributes': {'http.method': 'GET'}
        }
        assert adapter._is_genai_span(regular_span) is False
    
    def test_span_to_gdr(self):
        """Test converting span to GDR."""
        adapter = OTelAdapter()
        
        span = {
            'span_id': 'span-001',
            'trace_id': 'trace-001',
            'attributes': {
                'gen_ai.system': 'openai',
                'gen_ai.request.model': 'gpt-4',
                'gen_ai.usage.total_tokens': 1000
            }
        }
        
        gdr = adapter._span_to_gdr(span)
        
        assert gdr is not None
        assert gdr['subject']['capability_id'] == 'gpt-4'
        assert gdr['schema_version'] == '2.0.0'
    
    def test_extract_exceptions_error(self):
        """Test extracting exceptions from span with error status."""
        adapter = OTelAdapter()
        
        span = {
            'span_id': 'span-001',
            'status': {
                'code': 'ERROR',
                'description': 'Span execution failed'
            }
        }
        
        exceptions = adapter._extract_exceptions(span)
        
        assert len(exceptions) == 1
        assert exceptions[0]['category'] == 'capability_dead'
        assert exceptions[0]['severity'] == 'high'
    
    def test_extract_exceptions_high_latency(self):
        """Test extracting exceptions from span with high latency."""
        adapter = OTelAdapter()
        
        span = {
            'span_id': 'span-001',
            'start_time_nanos': 0,
            'end_time_nanos': 35_000_000_000  # 35 seconds
        }
        
        exceptions = adapter._extract_exceptions(span)
        
        assert len(exceptions) == 1
        assert exceptions[0]['category'] == 'run_cost_blowout'
        assert exceptions[0]['severity'] == 'medium'
    
    def test_extract_exceptions_high_tokens(self):
        """Test extracting exceptions from span with high token count."""
        adapter = OTelAdapter()
        
        span = {
            'span_id': 'span-001',
            'attributes': {
                'gen_ai.usage.total_tokens': 15000
            }
        }
        
        exceptions = adapter._extract_exceptions(span)
        
        assert len(exceptions) == 1
        assert exceptions[0]['category'] == 'run_cost_blowout'
        assert exceptions[0]['severity'] == 'medium'
    
    def test_extract_cost_from_attributes(self):
        """Test extracting cost from span attributes."""
        adapter = OTelAdapter()
        
        span = {
            'attributes': {
                'gen_ai.cost': 0.50
            }
        }
        
        cost = adapter._extract_cost(span)
        
        assert cost == 0.50
    
    def test_extract_cost_estimated(self):
        """Test estimating cost from token count."""
        adapter = OTelAdapter()
        
        span = {
            'attributes': {
                'gen_ai.usage.total_tokens': 1000,
                'gen_ai.request.model': 'gpt-4'
            }
        }
        
        cost = adapter._extract_cost(span)
        
        assert cost > 0  # Should estimate cost
    
    def test_infer_verdict_error(self):
        """Test inferring verdict from span with error."""
        adapter = OTelAdapter()
        
        span = {
            'status': {'code': 'ERROR'}
        }
        verdict = adapter._infer_verdict(span)
        
        assert verdict == 'destructive'
    
    def test_infer_verdict_healthy(self):
        """Test inferring verdict from healthy span."""
        adapter = OTelAdapter()
        
        span = {
            'status': {'code': 'OK'},
            'attributes': {'gen_ai.usage.total_tokens': 100}
        }
        verdict = adapter._infer_verdict(span)
        
        assert verdict == 'healthy'
    
    @patch('integrations.otel.OpenTrajectoryExporter')
    def test_emit_opentrajectory(self, mock_exporter):
        """Test emitting OpenTrajectory format."""
        adapter = OTelAdapter()
        
        mock_exporter_instance = Mock()
        mock_exporter_instance.to_opentrajectory.return_value = {'version': '0.1'}
        mock_exporter.return_value = mock_exporter_instance
        
        spans = [
            {
                'span_id': 'span-001',
                'trace_id': 'trace-001',
                'attributes': {
                    'gen_ai.system': 'openai',
                    'gen_ai.request.model': 'gpt-4'
                }
            }
        ]
        
        trajectories = adapter.emit_opentrajectory(spans)
        
        assert len(trajectories) == 1
