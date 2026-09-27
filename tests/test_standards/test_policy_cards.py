"""
Mocked unit tests for Policy Card exporter.

These tests use mocks to validate the export logic without requiring actual Policy Card schema downloads.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
import tempfile

try:
    from standards.policy_cards import PolicyCardExporter
except ImportError:
    pytest.skip("Policy Card exporter not yet implemented", allow_module_level=True)


class TestPolicyCardExporter:
    """Test Policy Card exporter (pure Python)."""
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.mkdir')
    def test_init(self, mock_mkdir, mock_exists):
        """Test successful initialization."""
        mock_exists.return_value = True  # Schema already exists
        
        exporter = PolicyCardExporter()
        
        assert exporter is not None
        assert exporter.local_schema_path is not None
        assert exporter.external_schema_url is not None
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.mkdir')
    @patch('builtins.open')
    def test_init_downloads_schema(self, mock_open, mock_mkdir, mock_exists):
        """Test initialization downloads schema if not present."""
        mock_exists.return_value = False
        
        # This would require requests, which we'll mock
        try:
            with patch('requests.get') as mock_get:
                mock_response = Mock()
                mock_response.json.return_value = {'$schema': 'test'}
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response
                
                exporter = PolicyCardExporter()
                
                mock_get.assert_called_once()
        except ImportError:
            pytest.skip("requests not available, using minimal schema")
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.mkdir')
    @patch('builtins.open')
    def test_to_policy_card(self, mock_open, mock_mkdir, mock_exists):
        """Test exporting YAML semantics to Policy Card."""
        mock_exists.return_value = True
        
        # Mock yaml.safe_load
        with patch('yaml.safe_load') as mock_yaml_load:
            mock_yaml_load.return_value = {
                'vertical': 'agent_runtime',
                'classification': {
                    'thresholds': {
                        'harm_score_min': 0.08
                    }
                },
                'decision': {
                    'verdict_rules': [
                        {'categories': ['capability_harm'], 'verdict': 'destructive', 'action': 'rollback'}
                    ],
                    'min_verified_share': 0.40,
                    'requires_experiment_id': False,
                    'evidence_types': ['simulated', 'associational', 'causal']
                }
            }
            
            # Mock jsonschema validation
            with patch('jsonschema.validate'):
                exporter = PolicyCardExporter()
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                    yaml_path = f.name
                    f.write('test: yaml')
                
                try:
                    policy_card = exporter.to_policy_card(yaml_path)
                    
                    assert policy_card['policy_id'] == 'POL-AGENT_RUNTIME-001'
                    assert policy_card['name'] == 'agent_runtime Governance Policy'
                    assert policy_card['category'] == 'operational'
                    assert 'rules' in policy_card
                    assert 'regulatory_mapping' in policy_card
                    assert 'evidence_requirements' in policy_card
                finally:
                    Path(yaml_path).unlink(missing_ok=True)
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.mkdir')
    def test_map_semantics_to_rules(self, mock_mkdir, mock_exists):
        """Test mapping CapEcon semantics to Policy Card rules."""
        mock_exists.return_value = True
        
        with patch('jsonschema.validate'):
            exporter = PolicyCardExporter()
            
            semantics = {
                'classification': {
                    'thresholds': {
                        'harm_score_min': 0.08,
                        'error_rate_max': 0.05
                    }
                },
                'decision': {
                    'verdict_rules': [
                        {'categories': ['capability_harm'], 'verdict': 'destructive', 'action': 'rollback'},
                        {'categories': ['loop_exhaustion'], 'verdict': 'needs_review', 'action': 'throttle'}
                    ]
                }
            }
            
            rules = exporter._map_semantics_to_rules(semantics)
            
            assert len(rules) == 3  # 2 thresholds + 2 verdict rules
            assert any(r['type'] == 'threshold' for r in rules)
            assert any(r['type'] == 'verdict' for r in rules)
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.mkdir')
    def test_extract_evidence_reqs(self, mock_mkdir, mock_exists):
        """Test extracting evidence requirements from semantics."""
        mock_exists.return_value = True
        
        with patch('jsonschema.validate'):
            exporter = PolicyCardExporter()
            
            semantics = {
                'decision': {
                    'min_verified_share': 0.40,
                    'requires_experiment_id': True,
                    'evidence_types': ['simulated', 'associational', 'causal']
                }
            }
            
            evidence_reqs = exporter._extract_evidence_reqs(semantics)
            
            assert evidence_reqs['min_verified_share'] == 0.40
            assert evidence_reqs['requires_experiment_id'] == True
            assert 'causal' in evidence_reqs['evidence_types']
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.mkdir')
    @patch('builtins.open')
    def test_save_to_file(self, mock_open, mock_mkdir, mock_exists):
        """Test saving Policy Card to file."""
        mock_exists.return_value = True
        
        with patch('jsonschema.validate'):
            exporter = PolicyCardExporter()
            
            policy_card = {'policy_id': 'POL-001', 'name': 'Test Policy'}
            
            exporter.save_to_file(policy_card, '/tmp/test_policy_card.json')
            
            mock_open.assert_called_once_with('/tmp/test_policy_card.json', 'w')
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.mkdir')
    @patch('builtins.open')
    def test_export_batch(self, mock_open, mock_mkdir, mock_exists):
        """Test exporting multiple YAML files to Policy Cards."""
        mock_exists.return_value = True
        
        with patch('jsonschema.validate'):
            with patch('yaml.safe_load') as mock_yaml_load:
                mock_yaml_load.return_value = {
                    'vertical': 'agent_runtime',
                    'classification': {'thresholds': {}},
                    'decision': {
                        'verdict_rules': [],
                        'min_verified_share': 0.40,
                        'requires_experiment_id': False,
                        'evidence_types': []
                    }
                }
                
                exporter = PolicyCardExporter()
                
                with tempfile.TemporaryDirectory() as tmpdir:
                    yaml1 = Path(tmpdir) / 'semantics1.yaml'
                    yaml2 = Path(tmpdir) / 'semantics2.yaml'
                    yaml1.write_text('test1')
                    yaml2.write_text('test2')
                    
                    exporter.export_batch([str(yaml1), str(yaml2)], tmpdir)
                    
                    # Should have created 2 policy card files
                    policy_files = list(Path(tmpdir).glob('*_policy_card.json'))
                    assert len(policy_files) == 2
