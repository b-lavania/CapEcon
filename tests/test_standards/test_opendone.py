"""
Mocked unit tests for OpenDone exporter.

These tests use mocks to avoid requiring actual Node.js/OpenDone installations.
They test the export logic and subprocess bridge structure.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

# We'll need to handle the import since the module may not exist yet
try:
    from standards.opendone import OpenDoneExporter
except ImportError:
    pytest.skip("OpenDone exporter not yet implemented", allow_module_level=True)


class TestOpenDoneExporter:
    """Test OpenDone exporter with mocked subprocess calls."""
    
    @patch('subprocess.run')
    def test_init_success(self, mock_run):
        """Test successful initialization when OpenDone is available."""
        mock_run.return_value = Mock(returncode=0, stdout="opendone v1.0.0")
        
        exporter = OpenDoneExporter()
        
        assert exporter is not None
        mock_run.assert_called_once_with(
            ["npx", "opendone", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
    
    @patch('subprocess.run')
    def test_init_nodejs_not_found(self, mock_run):
        """Test initialization fails when Node.js is not found."""
        mock_run.side_effect = FileNotFoundError()
        
        with pytest.raises(RuntimeError) as exc_info:
            OpenDoneExporter()
        
        assert "Node.js not found" in str(exc_info.value)
        assert "See README.md" in str(exc_info.value)
    
    @patch('subprocess.run')
    def test_init_opendone_not_installed(self, mock_run):
        """Test initialization fails when OpenDone is not installed."""
        mock_run.return_value = Mock(returncode=1, stderr="command not found")
        
        with pytest.raises(RuntimeError) as exc_info:
            OpenDoneExporter()
        
        assert "OpenDone not available" in str(exc_info.value)
        assert "npm install -g opendone" in str(exc_info.value)
    
    @patch('subprocess.run')
    def test_to_opendone_contract(self, mock_run):
        """Test exporting outcome definition to OpenDone contract."""
        # Mock the availability check
        mock_run.return_value = Mock(returncode=0, stdout="opendone v1.0.0")
        
        exporter = OpenDoneExporter()
        
        # Mock the validate call
        mock_run.return_value = Mock(returncode=0)
        
        outcome_def = {
            'task': 'test task',
            'outcome_types': ['verified_outcome'],
            'verified_by': {'verified_outcome': 'human_confirmation'},
            'max_duration_ms': 30000,
            'max_iterations': 10
        }
        
        contract = exporter.to_opendone_contract(outcome_def)
        
        assert contract['task'] == 'test task'
        assert 'criteria' in contract
        assert 'constraints' in contract
        assert contract['constraints']['maxDurationMs'] == 30000
        assert contract['constraints']['maxIterations'] == 10
    
    @patch('subprocess.run')
    def test_to_opendone_receipt(self, mock_run):
        """Test exporting GDR to OpenDone receipt."""
        # Mock the availability check
        mock_run.return_value = Mock(returncode=0, stdout="opendone v1.0.0")
        
        exporter = OpenDoneExporter()
        
        # Mock the validate and evaluate calls
        mock_run.return_value = Mock(returncode=0)
        
        gdr = {
            'record_id': 'test-gdr-001',
            'subject': {'agent_id': 'agent-001'},
            'outcome': {'verified': True},
            'decision': {'verdict': 'healthy'},
            'economics': {'floor_usd': 0.50},
            'runtime_duration_ms': 5000,
            'iteration_count': 3,
            'outcome_contract': {
                'task': 'test task',
                'outcome_types': ['verified_outcome']
            }
        }
        
        # Since we're mocking, we need to mock the receipt generation
        with patch.object(exporter, 'to_opendone_contract', return_value={'task': 'test'}):
            with patch('json.loads', return_value={'passed': True}):
                receipt = exporter.to_opendone_receipt(gdr)
        
        assert receipt is not None
    
    def test_map_verification_rules(self):
        """Test mapping CapEcon verification rules to OpenDone conditions."""
        with patch('subprocess.run', return_value=Mock(returncode=0, stdout="v1.0.0")):
            exporter = OpenDoneExporter()
            
            outcome_def = {
                'verified_by': {
                    'verified_outcome': 'human_confirmation',
                    'automated_check': 'deterministic_stage',
                    'llm_validation': 'llm_judge',
                    'external_validation': 'webhook'
                }
            }
            
            conditions = exporter._map_verification_rules(outcome_def)
            
            assert conditions['verified_outcome']['type'] == 'manual'
            assert conditions['automated_check']['type'] == 'deterministic'
            assert conditions['llm_validation']['type'] == 'automated'
            assert conditions['external_validation']['type'] == 'external'
    
    @patch('subprocess.run')
    def test_export_batch(self, mock_run):
        """Test exporting multiple GDRs."""
        mock_run.return_value = Mock(returncode=0, stdout="v1.0.0")
        
        exporter = OpenDoneExporter()
        
        gdrs = [
            {
                'record_id': 'gdr-001',
                'subject': {'agent_id': 'agent-001'},
                'outcome': {},
                'decision': {'verdict': 'healthy'},
                'economics': {'floor_usd': 0.50},
                'outcome_contract': {'task': 'task1', 'outcome_types': []}
            },
            {
                'record_id': 'gdr-002',
                'subject': {'agent_id': 'agent-002'},
                'outcome': {},
                'decision': {'verdict': 'healthy'},
                'economics': {'floor_usd': 0.75},
                'outcome_contract': {'task': 'task2', 'outcome_types': []}
            }
        ]
        
        with patch.object(exporter, 'to_opendone_contract', return_value={'task': 'test'}):
            with patch('json.loads', return_value={'passed': True}):
                receipts = exporter.export_batch(gdrs)
        
        assert len(receipts) == 2
