"""
Mocked unit tests for OpenTrajectory exporter.

These tests use mocks to validate the export logic without requiring actual OpenTrajectory dependencies.
"""

import pytest
from unittest.mock import Mock, patch

try:
    from standards.opentrajectory import OpenTrajectoryExporter
except ImportError:
    pytest.skip("OpenTrajectory exporter not yet implemented", allow_module_level=True)


class TestOpenTrajectoryExporter:
    """Test OpenTrajectory exporter (pure Python, no subprocess)."""
    
    def test_init(self):
        """Test successful initialization."""
        exporter = OpenTrajectoryExporter()
        assert exporter.version == "0.1"
    
    def test_init_custom_version(self):
        """Test initialization with custom version."""
        exporter = OpenTrajectoryExporter(version="0.2")
        assert exporter.version == "0.2"
    
    def test_to_opentrajectory(self):
        """Test exporting GDR to OpenTrajectory format."""
        exporter = OpenTrajectoryExporter()
        
        gdr = {
            'record_id': 'test-gdr-001',
            'subject': {'agent_id': 'agent-001', 'agent_type': 'agent'},
            'exceptions': [
                {
                    'exception_id': 'exc-001',
                    'category': 'capability_harm',
                    'description': 'Test exception',
                    'severity': 'high',
                    'owner_role': 'product',
                    'playbook_hint': 'Test hint'
                }
            ],
            'decision': {'verdict': 'healthy'},
            'outcome': {'verified_by': 'human_confirmation'},
            'evidence': {'confidence': 0.95}
        }
        
        trajectory = exporter.to_opentrajectory(gdr)
        
        assert trajectory['version'] == "0.1"
        assert trajectory['run_id'] == 'test-gdr-001'
        assert trajectory['agent_id'] == 'agent-001'
        assert len(trajectory['steps']) == 1
        assert trajectory['outcome']['success'] == True
        assert trajectory['outcome']['verified'] == True
        assert trajectory['verdict']['classification'] == 'success'
        assert trajectory['verdict']['confidence'] == 0.95
    
    def test_map_exceptions_to_steps(self):
        """Test mapping CapEcon exceptions to OpenTrajectory steps."""
        exporter = OpenTrajectoryExporter()
        
        exceptions = [
            {
                'exception_id': 'exc-001',
                'category': 'capability_harm',
                'description': 'Harmful capability',
                'severity': 'high',
                'owner_role': 'product',
                'playbook_hint': 'Review immediately'
            },
            {
                'exception_id': 'exc-002',
                'category': 'run_cost_blowout',
                'description': 'Cost exceeded',
                'severity': 'medium',
                'owner_role': 'engineering',
                'playbook_hint': 'Optimize prompts'
            }
        ]
        
        steps = exporter._map_exceptions_to_steps(exceptions)
        
        assert len(steps) == 2
        assert steps[0]['step_type'] == 'capability_harm'
        assert steps[0]['severity'] == 'high'
        assert steps[1]['step_type'] == 'run_cost_blowout'
        assert steps[1]['severity'] == 'medium'
    
    def test_map_verdict_to_ot_verdict(self):
        """Test mapping CapEcon verdicts to OpenTrajectory verdicts."""
        exporter = OpenTrajectoryExporter()
        
        verdict_map = {
            'healthy': 'success',
            'leaking': 'failure',
            'destructive': 'failure',
            'uneconomic': 'failure',
            'underpowered': 'failure',
            'needs_review': 'unknown'
        }
        
        for cap_verdict, expected_ot_verdict in verdict_map.items():
            ot_verdict = exporter._map_verdict_to_ot_verdict(cap_verdict)
            assert ot_verdict == expected_ot_verdict
        
        # Test unknown verdict
        unknown_verdict = exporter._map_verdict_to_ot_verdict('unknown')
        assert unknown_verdict == 'unknown'
    
    def test_export_batch(self):
        """Test exporting multiple GDRs."""
        exporter = OpenTrajectoryExporter()
        
        gdrs = [
            {
                'record_id': 'gdr-001',
                'subject': {'agent_id': 'agent-001'},
                'exceptions': [],
                'decision': {'verdict': 'healthy'},
                'outcome': {},
                'evidence': {'confidence': 0.9}
            },
            {
                'record_id': 'gdr-002',
                'subject': {'agent_id': 'agent-002'},
                'exceptions': [],
                'decision': {'verdict': 'leaking'},
                'outcome': {},
                'evidence': {'confidence': 0.8}
            }
        ]
        
        trajectories = exporter.export_batch(gdrs)
        
        assert len(trajectories) == 2
        assert trajectories[0]['run_id'] == 'gdr-001'
        assert trajectories[1]['run_id'] == 'gdr-002'
        assert trajectories[0]['verdict']['classification'] == 'success'
        assert trajectories[1]['verdict']['classification'] == 'failure'
    
    @patch('builtins.open')
    def test_save_to_file(self, mock_open):
        """Test saving trajectory to file."""
        exporter = OpenTrajectoryExporter()
        
        trajectory = {'version': '0.1', 'run_id': 'test'}
        
        exporter.save_to_file(trajectory, '/tmp/test.ot.json')
        
        mock_open.assert_called_once_with('/tmp/test.ot.json', 'w')
    
    @patch('pathlib.Path.mkdir')
    @patch('builtins.open')
    def test_save_batch_to_files(self, mock_open, mock_mkdir):
        """Test saving multiple trajectories to files."""
        exporter = OpenTrajectoryExporter()
        
        trajectories = [
            {'version': '0.1', 'run_id': 'gdr-001'},
            {'version': '0.1', 'run_id': 'gdr-002'}
        ]
        
        exporter.save_batch_to_files(trajectories, '/tmp/output')
        
        assert mock_mkdir.called
        assert mock_open.call_count == 2
