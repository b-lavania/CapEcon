"""
Mocked unit tests for ADP validator.

These tests use mocks to avoid requiring actual Node.js/ADP installations.
They test the validation logic and subprocess bridge structure.
"""

import pytest
from unittest.mock import Mock, patch

try:
    from standards.adp import ADPValidator
except ImportError:
    pytest.skip("ADP validator not yet implemented", allow_module_level=True)


class TestADPValidator:
    """Test ADP validator with mocked subprocess calls."""
    
    @patch('subprocess.run')
    def test_init_success(self, mock_run):
        """Test successful initialization when ADP is available."""
        mock_run.return_value = Mock(returncode=0, stdout="@adp/core v1.0.0")
        
        validator = ADPValidator()
        
        assert validator is not None
        mock_run.assert_called_once_with(
            ["npx", "@adp/core", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
    
    @patch('subprocess.run')
    def test_init_nodejs_not_found(self, mock_run):
        """Test initialization fails when Node.js is not found."""
        mock_run.side_effect = FileNotFoundError()
        
        with pytest.raises(RuntimeError) as exc_info:
            ADPValidator()
        
        assert "Node.js not found" in str(exc_info.value)
        assert "See README.md" in str(exc_info.value)
    
    @patch('subprocess.run')
    def test_init_adp_not_installed(self, mock_run):
        """Test initialization fails when ADP is not installed."""
        mock_run.return_value = Mock(returncode=1, stderr="command not found")
        
        with pytest.raises(RuntimeError) as exc_info:
            ADPValidator()
        
        assert "ADP not available" in str(exc_info.value)
        assert "npm install -g @adp/core" in str(exc_info.value)
    
    @patch('subprocess.run')
    def test_infer_autonomy(self, mock_run):
        """Test inferring autonomy level from subject."""
        mock_run.return_value = Mock(returncode=0, stdout="v1.0.0")
        
        validator = ADPValidator()
        
        # Test different agent types
        assert validator._infer_autonomy({'agent_type': 'human'}) == 'A1'
        assert validator._infer_autonomy({'agent_type': 'tool'}) == 'A2'
        assert validator._infer_autonomy({'agent_type': 'assistant'}) == 'A3'
        assert validator._infer_autonomy({'agent_type': 'agent'}) == 'A4'
        assert validator._infer_autonomy({'agent_type': 'unknown'}) == 'A5'
    
    @patch('subprocess.run')
    def test_classify_decision_type(self, mock_run):
        """Test classifying decision type from GDR."""
        mock_run.return_value = Mock(returncode=0, stdout="v1.0.0")
        
        validator = ADPValidator()
        
        # Test operational decisions
        gdr_operational = {'decision': {'recommended_action': 'ship'}}
        assert validator._classify_decision_type(gdr_operational) == 'operational'
        
        # Test strategic decisions
        gdr_strategic = {'decision': {'recommended_action': 'experiment'}}
        assert validator._classify_decision_type(gdr_strategic) == 'strategic'
        
        # Test financial decisions
        gdr_financial = {'decision': {'commercial_action': 'raise_list'}}
        assert validator._classify_decision_type(gdr_financial) == 'financial'
    
    @patch('subprocess.run')
    def test_classify_risk(self, mock_run):
        """Test classifying risk level from GDR."""
        mock_run.return_value = Mock(returncode=0, stdout="v1.0.0")
        
        validator = ADPValidator()
        
        # Test different verdicts
        gdr_critical = {'decision': {'verdict': 'destructive'}}
        assert validator._classify_risk(gdr_critical) == 'critical'
        
        gdr_high = {'decision': {'verdict': 'leaking'}}
        assert validator._classify_risk(gdr_high) == 'high'
        
        gdr_medium = {'decision': {'verdict': 'needs_review'}}
        assert validator._classify_risk(gdr_medium) == 'medium'
        
        gdr_low = {'decision': {'verdict': 'healthy'}}
        assert validator._classify_risk(gdr_low) == 'low'
    
    @patch('subprocess.run')
    def test_get_authorization(self, mock_run):
        """Test getting authorization matrix result."""
        mock_run.return_value = Mock(returncode=0, stdout="v1.0.0")
        
        validator = ADPValidator()
        
        # Test low autonomy
        auth = validator._get_authorization('A1', 'operational')
        assert auth['result'] == 'approval_required'
        
        # Test high autonomy
        auth = validator._get_authorization('A5', 'operational')
        assert auth['result'] == 'auto_approved'
        
        # Test medium autonomy with strategic decision
        auth = validator._get_authorization('A3', 'strategic')
        assert auth['result'] == 'approval_required'
    
    @patch('subprocess.run')
    @patch('json.loads')
    def test_add_adp_metadata(self, mock_json_loads, mock_run):
        """Test adding ADP metadata to GDR."""
        mock_run.return_value = Mock(returncode=0, stdout="v1.0.0")
        mock_json_loads.return_value = {'classification_code': 'operational-medium'}
        
        validator = ADPValidator()
        
        gdr = {
            'record_id': 'test-gdr-001',
            'subject': {'agent_id': 'agent-001', 'agent_type': 'agent'},
            'decision': {'verdict': 'healthy', 'recommended_action': 'ship', 'requires_review': False}
        }
        
        enhanced_gdr = validator.add_adp_metadata(gdr)
        
        assert 'adp' in enhanced_gdr
        assert enhanced_gdr['adp']['autonomy_level'] == 'A4'
        assert enhanced_gdr['adp']['decision_type'] == 'operational'
        assert enhanced_gdr['adp']['risk_level'] == 'low'
        assert enhanced_gdr['adp']['classification_code'] == 'operational-medium'
        assert 'authorization' in enhanced_gdr['adp']
    
    @patch('subprocess.run')
    @patch('json.loads')
    def test_add_adp_metadata_override_requires_review(self, mock_json_loads, mock_run):
        """Test ADP overriding requires_review for regulatory compliance."""
        mock_run.return_value = Mock(returncode=0, stdout="v1.0.0")
        mock_json_loads.return_value = {'classification_code': 'operational-critical'}
        
        validator = ADPValidator()
        
        gdr = {
            'record_id': 'test-gdr-001',
            'subject': {'agent_id': 'agent-001', 'agent_type': 'tool'},
            'decision': {'verdict': 'healthy', 'recommended_action': 'ship', 'requires_review': False}
        }
        
        enhanced_gdr = validator.add_adp_metadata(gdr)
        
        # Low autonomy should trigger approval_required
        assert enhanced_gdr['decision']['requires_review'] == True
        assert 'ADP regulatory override' in enhanced_gdr['decision']['requires_review_reason']
    
    @patch('subprocess.run')
    def test_validate_batch(self, mock_run):
        """Test validating multiple GDRs."""
        mock_run.return_value = Mock(returncode=0, stdout="v1.0.0")
        
        validator = ADPValidator()
        
        gdrs = [
            {
                'record_id': 'gdr-001',
                'subject': {'agent_id': 'agent-001', 'agent_type': 'agent'},
                'decision': {'verdict': 'healthy', 'recommended_action': 'ship'}
            },
            {
                'record_id': 'gdr-002',
                'subject': {'agent_id': 'agent-002', 'agent_type': 'agent'},
                'decision': {'verdict': 'healthy', 'recommended_action': 'ship'}
            }
        ]
        
        with patch('json.loads', return_value={'classification_code': 'operational-low'}):
            validated_gdrs = validator.validate_batch(gdrs)
        
        assert len(validated_gdrs) == 2
        assert 'adp' in validated_gdrs[0]
        assert 'adp' in validated_gdrs[1]
