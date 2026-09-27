"""
Mocked unit tests for AutoGen adapter.

These tests use mocks to validate the adapter logic without requiring actual AutoGen installations.
"""

import pytest
from unittest.mock import Mock, patch

try:
    from integrations.autogen import AutoGenAdapter
except ImportError:
    pytest.skip("AutoGen adapter not yet implemented", allow_module_level=True)


class TestAutoGenAdapter:
    """Test AutoGen adapter with mocked conversations."""
    
    def test_init(self):
        """Test successful initialization."""
        adapter = AutoGenAdapter()
        assert adapter.version == "1.0.0"
    
    def test_ingest_autogen_conversation(self):
        """Test ingesting AutoGen conversation."""
        adapter = AutoGenAdapter()
        
        conversation = {
            'conversation_id': 'test-conversation',
            'messages': [
                {
                    'message_id': 'msg-001',
                    'role': 'assistant',
                    'sender': 'agent-001',
                    'tool_name': 'general_assistant',
                    'cost_usd': 0.60,
                    'budget_cap': 10.0
                }
            ]
        }
        
        gdrs = adapter.ingest_autogen_conversation(conversation)
        
        assert len(gdrs) == 1
        assert gdrs[0]['subject']['capability_id'] == 'general_assistant'
        assert gdrs[0]['subject']['agent_id'] == 'agent-001'
        assert gdrs[0]['vertical'] == 'orchestration'
    
    def test_message_to_gdr(self):
        """Test converting message to GDR."""
        adapter = AutoGenAdapter()
        
        message = {
            'message_id': 'msg-001',
            'role': 'assistant',
            'sender': 'agent-001',
            'tool_name': 'general_assistant',
            'cost_usd': 0.60
        }
        
        conversation = {'conversation_id': 'test-conversation'}
        
        gdr = adapter._message_to_gdr(message, conversation)
        
        assert gdr is not None
        assert gdr['subject']['capability_id'] == 'general_assistant'
        assert gdr['economics']['floor_usd'] == 0.60
        assert gdr['schema_version'] == '2.0.0'
    
    def test_extract_exceptions_error(self):
        """Test extracting exceptions from message with error."""
        adapter = AutoGenAdapter()
        
        message = {
            'message_id': 'msg-001',
            'error': 'Message processing failed'
        }
        
        exceptions = adapter._extract_exceptions(message)
        
        assert len(exceptions) == 1
        assert exceptions[0]['category'] == 'capability_dead'
        assert exceptions[0]['severity'] == 'high'
    
    def test_extract_exceptions_tool_failure(self):
        """Test extracting exceptions from message with tool call failures."""
        adapter = AutoGenAdapter()
        
        message = {
            'message_id': 'msg-001',
            'tool_calls': [
                {'status': 'failed'},
                {'status': 'failed'}
            ]
        }
        
        exceptions = adapter._extract_exceptions(message)
        
        assert len(exceptions) == 1
        assert exceptions[0]['category'] == 'handoff_failure'
        assert exceptions[0]['severity'] == 'medium'
    
    def test_extract_exceptions_loop(self):
        """Test extracting exceptions from message with excessive message count."""
        adapter = AutoGenAdapter()
        
        message = {
            'message_id': 'msg-001',
            'conversation_message_count': 15
        }
        
        exceptions = adapter._extract_exceptions(message)
        
        assert len(exceptions) == 1
        assert exceptions[0]['category'] == 'loop_exhaustion'
        assert exceptions[0]['severity'] == 'high'
    
    def test_infer_verdict_error(self):
        """Test inferring verdict from message with error."""
        adapter = AutoGenAdapter()
        
        message = {'error': 'Message failed'}
        verdict = adapter._infer_verdict(message)
        
        assert verdict == 'destructive'
    
    def test_infer_verdict_healthy(self):
        """Test inferring verdict from healthy message."""
        adapter = AutoGenAdapter()
        
        message = {'conversation_message_count': 5}
        verdict = adapter._infer_verdict(message)
        
        assert verdict == 'healthy'
    
    @patch('integrations.autogen.OpenTrajectoryExporter')
    def test_emit_opentrajectory(self, mock_exporter):
        """Test emitting OpenTrajectory format."""
        adapter = AutoGenAdapter()
        
        mock_exporter_instance = Mock()
        mock_exporter_instance.to_opentrajectory.return_value = {'version': '0.1'}
        mock_exporter.return_value = mock_exporter_instance
        
        conversation = {
            'conversation_id': 'test-conversation',
            'messages': [
                {
                    'message_id': 'msg-001',
                    'role': 'assistant',
                    'sender': 'agent-001',
                    'tool_name': 'general_assistant'
                }
            ]
        }
        
        trajectories = adapter.emit_opentrajectory(conversation)
        
        assert len(trajectories) == 1
