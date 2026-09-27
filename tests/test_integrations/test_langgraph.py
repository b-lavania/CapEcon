"""
Mocked unit tests for LangGraph adapter.

These tests use mocks to validate the adapter logic without requiring actual LangGraph installations.
"""

import pytest
from unittest.mock import Mock, patch

try:
    from integrations.langgraph import LangGraphAdapter
except ImportError:
    pytest.skip("LangGraph adapter not yet implemented", allow_module_level=True)


class TestLangGraphAdapter:
    """Test LangGraph adapter with mocked traces."""
    
    def test_init(self):
        """Test successful initialization."""
        adapter = LangGraphAdapter()
        assert adapter.version == "1.0.0"
    
    def test_ingest_langgraph_trace(self):
        """Test ingesting LangGraph trace."""
        adapter = LangGraphAdapter()
        
        trace = {
            'workspace_id': 'test-workspace',
            'node_executions': [
                {
                    'node_id': 'node-001',
                    'node_name': 'test_node',
                    'agent_id': 'agent-001',
                    'cost_usd': 0.50,
                    'budget_cap': 10.0
                }
            ]
        }
        
        gdrs = adapter.ingest_langgraph_trace(trace)
        
        assert len(gdrs) == 1
        assert gdrs[0]['subject']['capability_id'] == 'test_node'
        assert gdrs[0]['subject']['agent_id'] == 'agent-001'
        assert gdrs[0]['vertical'] == 'agent_runtime'
    
    def test_node_execution_to_gdr(self):
        """Test converting node execution to GDR."""
        adapter = LangGraphAdapter()
        
        node_execution = {
            'node_id': 'node-001',
            'node_name': 'test_node',
            'agent_id': 'agent-001',
            'cost_usd': 0.50
        }
        
        trace = {'workspace_id': 'test-workspace'}
        
        gdr = adapter._node_execution_to_gdr(node_execution, trace)
        
        assert gdr is not None
        assert gdr['subject']['capability_id'] == 'test_node'
        assert gdr['economics']['floor_usd'] == 0.50
        assert gdr['schema_version'] == '2.0.0'
    
    def test_extract_exceptions_error(self):
        """Test extracting exceptions from node execution with error."""
        adapter = LangGraphAdapter()
        
        node_execution = {
            'node_id': 'node-001',
            'error': 'Node execution failed'
        }
        
        exceptions = adapter._extract_exceptions(node_execution)
        
        assert len(exceptions) == 1
        assert exceptions[0]['category'] == 'capability_dead'
        assert exceptions[0]['severity'] == 'high'
    
    def test_extract_exceptions_retry(self):
        """Test extracting exceptions from node execution with high retry count."""
        adapter = LangGraphAdapter()
        
        node_execution = {
            'node_id': 'node-001',
            'retry_count': 5
        }
        
        exceptions = adapter._extract_exceptions(node_execution)
        
        assert len(exceptions) == 1
        assert exceptions[0]['category'] == 'activation_leak'
        assert exceptions[0]['severity'] == 'medium'
    
    def test_infer_verdict_error(self):
        """Test inferring verdict from node execution with error."""
        adapter = LangGraphAdapter()
        
        node_execution = {'error': 'Node failed'}
        verdict = adapter._infer_verdict(node_execution)
        
        assert verdict == 'destructive'
    
    def test_infer_verdict_healthy(self):
        """Test inferring verdict from healthy node execution."""
        adapter = LangGraphAdapter()
        
        node_execution = {'retry_count': 0}
        verdict = adapter._infer_verdict(node_execution)
        
        assert verdict == 'healthy'
    
    @patch('integrations.langgraph.OpenTrajectoryExporter')
    def test_emit_opentrajectory(self, mock_exporter):
        """Test emitting OpenTrajectory format."""
        adapter = LangGraphAdapter()
        
        mock_exporter_instance = Mock()
        mock_exporter_instance.to_opentrajectory.return_value = {'version': '0.1'}
        mock_exporter.return_value = mock_exporter_instance
        
        trace = {
            'workspace_id': 'test-workspace',
            'node_executions': [
                {
                    'node_id': 'node-001',
                    'node_name': 'test_node',
                    'agent_id': 'agent-001'
                }
            ]
        }
        
        trajectories = adapter.emit_opentrajectory(trace)
        
        assert len(trajectories) == 1
