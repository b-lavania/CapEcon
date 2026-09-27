"""
Mocked unit tests for CrewAI adapter.

These tests use mocks to validate the adapter logic without requiring actual CrewAI installations.
"""

import pytest
from unittest.mock import Mock, patch

try:
    from integrations.crewai import CrewAIAdapter
except ImportError:
    pytest.skip("CrewAI adapter not yet implemented", allow_module_level=True)


class TestCrewAIAdapter:
    """Test CrewAI adapter with mocked traces."""
    
    def test_init(self):
        """Test successful initialization."""
        adapter = CrewAIAdapter()
        assert adapter.version == "1.0.0"
    
    def test_ingest_crew_trace(self):
        """Test ingesting CrewAI trace."""
        adapter = CrewAIAdapter()
        
        trace = {
            'crew_id': 'test-crew',
            'task_executions': [
                {
                    'task_id': 'task-001',
                    'task_name': 'test_task',
                    'agent_id': 'agent-001',
                    'cost_usd': 0.75,
                    'budget_cap': 10.0
                }
            ]
        }
        
        gdrs = adapter.ingest_crew_trace(trace)
        
        assert len(gdrs) == 1
        assert gdrs[0]['subject']['capability_id'] == 'test_task'
        assert gdrs[0]['subject']['agent_id'] == 'agent-001'
        assert gdrs[0]['vertical'] == 'orchestration'
    
    def test_task_execution_to_gdr(self):
        """Test converting task execution to GDR."""
        adapter = CrewAIAdapter()
        
        task_execution = {
            'task_id': 'task-001',
            'task_name': 'test_task',
            'agent_id': 'agent-001',
            'cost_usd': 0.75
        }
        
        trace = {'crew_id': 'test-crew'}
        
        gdr = adapter._task_execution_to_gdr(task_execution, trace)
        
        assert gdr is not None
        assert gdr['subject']['capability_id'] == 'test_task'
        assert gdr['economics']['floor_usd'] == 0.75
        assert gdr['schema_version'] == '2.0.0'
    
    def test_extract_exceptions_error(self):
        """Test extracting exceptions from task execution with error."""
        adapter = CrewAIAdapter()
        
        task_execution = {
            'task_id': 'task-001',
            'error': 'Task execution failed'
        }
        
        exceptions = adapter._extract_exceptions(task_execution)
        
        assert len(exceptions) == 1
        assert exceptions[0]['category'] == 'capability_dead'
        assert exceptions[0]['severity'] == 'high'
    
    def test_extract_exceptions_handoff_failed(self):
        """Test extracting exceptions from task execution with handoff failure."""
        adapter = CrewAIAdapter()
        
        task_execution = {
            'task_id': 'task-001',
            'handoff_failed': True
        }
        
        exceptions = adapter._extract_exceptions(task_execution)
        
        assert len(exceptions) == 1
        assert exceptions[0]['category'] == 'handoff_failure'
        assert exceptions[0]['severity'] == 'medium'
    
    def test_extract_exceptions_coordination_cost(self):
        """Test extracting exceptions from task execution with high coordination cost."""
        adapter = CrewAIAdapter()
        
        task_execution = {
            'task_id': 'task-001',
            'coordination_ratio': 0.40
        }
        
        exceptions = adapter._extract_exceptions(task_execution)
        
        assert len(exceptions) == 1
        assert exceptions[0]['category'] == 'coordination_cost'
        assert exceptions[0]['severity'] == 'medium'
    
    def test_infer_verdict_error(self):
        """Test inferring verdict from task execution with error."""
        adapter = CrewAIAdapter()
        
        task_execution = {'error': 'Task failed'}
        verdict = adapter._infer_verdict(task_execution)
        
        assert verdict == 'destructive'
    
    def test_infer_verdict_healthy(self):
        """Test inferring verdict from healthy task execution."""
        adapter = CrewAIAdapter()
        
        task_execution = {'coordination_ratio': 0.30}
        verdict = adapter._infer_verdict(task_execution)
        
        assert verdict == 'healthy'
    
    @patch('integrations.crewai.OpenTrajectoryExporter')
    def test_emit_opentrajectory(self, mock_exporter):
        """Test emitting OpenTrajectory format."""
        adapter = CrewAIAdapter()
        
        mock_exporter_instance = Mock()
        mock_exporter_instance.to_opentrajectory.return_value = {'version': '0.1'}
        mock_exporter.return_value = mock_exporter_instance
        
        trace = {
            'crew_id': 'test-crew',
            'task_executions': [
                {
                    'task_id': 'task-001',
                    'task_name': 'test_task',
                    'agent_id': 'agent-001'
                }
            ]
        }
        
        trajectories = adapter.emit_opentrajectory(trace)
        
        assert len(trajectories) == 1
