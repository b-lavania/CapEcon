"""
ADP (Agent Decision Protocol) validator for CapEcon.

This module adds ADP compliance metadata to CapEcon GrowthDecisionRecords.
ADP is an optional validation layer - CapEcon's triage system remains the primary triage mechanism.

ADP CLI is called via subprocess. If Node.js or @adp/core is not available,
this module will fail fast with a clear error message directing the user to README.md.

Critical: This is an OPTIONAL validation layer, not a replacement for CapEcon's triage system.
"""

import subprocess
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional


class ADPValidator:
    """
    Add ADP compliance as optional validation layer via subprocess.
    
    This validator calls the ADP CLI (npx @adp/core) to classify decisions and
    check authorization requirements. It requires Node.js and the @adp/core npm package.
    
    If Node.js or @adp/core is not available, initialization will fail fast
    with a clear error message.
    
    ADP adds OPTIONAL metadata to GDRs. It can OVERRIDE requires_review for
    regulatory compliance, but CapEcon's triage system (TRIAGE_STATES, ROLE_OWNERS)
    remains the primary triage mechanism.
    """
    
    def __init__(self):
        """Initialize ADP validator and check availability (fail fast if unavailable)."""
        self._check_adp_available()
    
    def _check_adp_available(self):
        """
        Check if npx @adp/core is available - fail fast if not.
        
        Raises:
            RuntimeError: If Node.js or @adp/core is not available, with clear setup instructions.
        """
        try:
            result = subprocess.run(
                ["npx", "@adp/core", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "ADP not available. Install with: npm install -g @adp/core\n"
                    "See README.md for Node.js setup instructions."
                )
        except FileNotFoundError:
            raise RuntimeError(
                "Node.js not found. ADP validation requires Node.js.\n"
                "Install Node.js from https://nodejs.org/ then: npm install -g @adp/core\n"
                "See README.md for setup instructions."
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "ADP CLI timed out. Check your network connection and try again."
            )
    
    def add_adp_metadata(self, gdr: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add ADP fields as optional metadata (NOT replacing CapEcon's triage).
        
        This method adds ADP autonomy level, decision type, risk level, and authorization
        metadata to the GDR. ADP can OVERRIDE requires_review for regulatory compliance,
        but CapEcon's triage system (TRIAGE_STATES, ROLE_OWNERS) remains the primary
        triage mechanism.
        
        Args:
            gdr: CapEcon GrowthDecisionRecord dictionary
        
        Returns:
            GDR dictionary with ADP metadata added
        
        Raises:
            RuntimeError: If ADP classification fails
        """
        autonomy_level = self._infer_autonomy(gdr.get('subject', {}))
        decision_type = self._classify_decision_type(gdr)
        risk_level = self._classify_risk(gdr)
        
        # Call ADP classify via subprocess
        classify_input = {
            'decision_type': decision_type,
            'risk_level': risk_level,
            'reversibility': 'partial'  # Default
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(classify_input, f)
            input_path = f.name
        
        try:
            result = subprocess.run(
                ["npx", "@adp/core", "classify", input_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                raise RuntimeError(f"ADP classify failed: {result.stderr}")
            adp_result = json.loads(result.stdout)
            adp_classification = adp_result.get('classification_code', f"{decision_type}-{risk_level}")
        finally:
            Path(input_path).unlink(missing_ok=True)
        
        # Add as OPTIONAL metadata field
        gdr['adp'] = {
            'autonomy_level': autonomy_level,
            'decision_type': decision_type,
            'risk_level': risk_level,
            'classification_code': adp_classification,
            'authorization': self._get_authorization(autonomy_level, decision_type)
        }
        
        # ADP can OVERRIDE requires_review for regulatory compliance
        # But CapEcon's triage system remains the primary triage mechanism
        if gdr['adp']['authorization']['result'] == 'approval_required':
            gdr['decision']['requires_review'] = True
            gdr['decision']['requires_review_reason'] = 'ADP regulatory override'
            
        return gdr
    
    def _infer_autonomy(self, subject: Dict[str, Any]) -> str:
        """
        Infer ADP autonomy level from GDR subject.
        
        ADP autonomy levels: A1 (no autonomy) to A5 (full autonomy)
        This is a heuristic mapping based on CapEcon's subject structure.
        
        Args:
            subject: GDR subject dictionary
        
        Returns:
            Autonomy level string (A1-A5)
        """
        # Placeholder implementation - refine based on actual subject structure
        agent_type = subject.get('agent_type', 'unknown')
        
        if agent_type == 'human':
            return 'A1'  # No autonomy
        elif agent_type == 'tool':
            return 'A2'  # Tool-level autonomy
        elif agent_type == 'assistant':
            return 'A3'  # Assistant-level autonomy
        elif agent_type == 'agent':
            return 'A4'  # Agent-level autonomy
        else:
            return 'A5'  # Full autonomy (default)
    
    def _classify_decision_type(self, gdr: Dict[str, Any]) -> str:
        """
        Classify decision type from GDR.
        
        ADP decision types: operational, strategic, financial, regulatory
        This maps CapEcon's decision structure to ADP types.
        
        Args:
            gdr: CapEcon GrowthDecisionRecord dictionary
        
        Returns:
            Decision type string
        """
        decision = gdr.get('decision', {})
        recommended_action = decision.get('recommended_action', '')
        
        # Map CapEcon actions to ADP decision types
        if recommended_action in ['ship', 'hold', 'throttle', 'shadow', 'rollback', 'kill']:
            return 'operational'
        elif recommended_action in ['experiment', 'revise']:
            return 'strategic'
        elif 'commercial_action' in decision:
            return 'financial'
        else:
            return 'operational'  # Default
    
    def _classify_risk(self, gdr: Dict[str, Any]) -> str:
        """
        Classify risk level from GDR.
        
        ADP risk levels: low, medium, high, critical
        This maps CapEcon's verdict and exceptions to ADP risk levels.
        
        Args:
            gdr: CapEcon GrowthDecisionRecord dictionary
        
        Returns:
            Risk level string
        """
        verdict = gdr.get('decision', {}).get('verdict', '')
        exceptions = gdr.get('exceptions', [])
        
        # Map CapEcon verdicts to ADP risk levels
        if verdict == 'destructive':
            return 'critical'
        elif verdict in ['leaking', 'uneconomic']:
            return 'high'
        elif verdict == 'needs_review':
            return 'medium'
        else:
            # Check exception severity
            for exc in exceptions:
                if exc.get('severity') == 'high':
                    return 'high'
            return 'low'
    
    def _get_authorization(self, autonomy_level: str, decision_type: str) -> Dict[str, Any]:
        """
        Get authorization matrix result.
        
        ADP authorization matrix determines when human approval is required.
        This is a simplified version of the full ADP authorization matrix.
        
        Args:
            autonomy_level: ADP autonomy level (A1-A5)
            decision_type: ADP decision type
        
        Returns:
            Authorization dictionary with result and reason
        """
        # Simplified authorization matrix
        # In production, this would call the full ADP authorization matrix
        if autonomy_level in ['A1', 'A2']:
            return {
                'result': 'approval_required',
                'reason': f'Autonomy level {autonomy_level} requires approval for {decision_type} decisions'
            }
        elif autonomy_level == 'A3' and decision_type in ['strategic', 'financial']:
            return {
                'result': 'approval_required',
                'reason': f'Autonomy level {autonomy_level} requires approval for {decision_type} decisions'
            }
        else:
            return {
                'result': 'auto_approved',
                'reason': f'Autonomy level {autonomy_level} allows auto-approval for {decision_type} decisions'
            }
    
    def validate_batch(self, gdrs: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """
        Add ADP metadata to multiple GDRs.
        
        Args:
            gdrs: List of CapEcon GrowthDecisionRecord dictionaries
        
        Returns:
            List of GDR dictionaries with ADP metadata added
        """
        validated_gdrs = []
        for gdr in gdrs:
            try:
                validated_gdr = self.add_adp_metadata(gdr)
                validated_gdrs.append(validated_gdr)
            except RuntimeError as e:
                # Log error but continue with other GDRs
                print(f"Failed to validate GDR {gdr.get('record_id', 'unknown')}: {e}")
                validated_gdrs.append(gdr)  # Add original GDR without ADP metadata
        return validated_gdrs


# CRITICAL: ADP is an OPTIONAL validation layer, not a replacement
# CapEcon's triage system (TRIAGE_STATES, ROLE_OWNERS) remains primary
# ADP adds regulatory compliance checking on top
