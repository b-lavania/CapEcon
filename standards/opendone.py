"""
OpenDone exporter for CapEcon.

This module exports CapEcon GrowthDecisionRecords to OpenDone receipt format.
OpenDone is an optional export format - CapEcon's internal GDR format remains the primary format.

OpenDone CLI is called via subprocess. If Node.js or opendone is not available,
this module will fail fast with a clear error message directing the user to README.md.

Critical: This is an EXPORT layer, not a replacement for CapEcon's Outcome Definition Kit.
"""

import subprocess
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional


class OpenDoneExporter:
    """
    Export CapEcon GDR to OpenDone receipt format via subprocess.
    
    This exporter calls the OpenDone CLI (npx opendone) to validate contracts
    and generate receipts. It requires Node.js and the opendone npm package.
    
    If Node.js or opendone is not available, initialization will fail fast
    with a clear error message.
    """
    
    def __init__(self):
        """Initialize OpenDone exporter and check availability (fail fast if unavailable)."""
        self._check_opendone_available()
    
    def _check_opendone_available(self):
        """
        Check if npx opendone is available - fail fast if not.
        
        Raises:
            RuntimeError: If Node.js or opendone is not available, with clear setup instructions.
        """
        try:
            result = subprocess.run(
                ["npx", "opendone", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "OpenDone not available. Install with: npm install -g opendone\n"
                    "See README.md for Node.js setup instructions."
                )
        except FileNotFoundError:
            raise RuntimeError(
                "Node.js not found. OpenDone export requires Node.js.\n"
                "Install Node.js from https://nodejs.org/ then: npm install -g opendone\n"
                "See README.md for setup instructions."
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "OpenDone CLI timed out. Check your network connection and try again."
            )
    
    def to_opendone_contract(self, outcome_def: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export CapEcon Outcome Definition to OpenDone Contract.
        
        Maps CapEcon's richer outcome definition structure to OpenDone's simpler contract format.
        This is an EXPORT - CapEcon's Outcome Definition Kit remains the primary format.
        
        Args:
            outcome_def: CapEcon outcome definition dictionary from ontology/outcome_contract.py
        
        Returns:
            OpenDone contract dictionary
        
        Raises:
            RuntimeError: If OpenDone validation fails
        """
        # Map CapEcon's richer structure to OpenDone's simpler contract
        contract_dict = {
            'task': outcome_def.get('task', ''),
            'criteria': {
                'required': outcome_def.get('outcome_types', []),
                'conditions': self._map_verification_rules(outcome_def)
            },
            'constraints': {
                'maxDurationMs': outcome_def.get('max_duration_ms'),
                'maxIterations': outcome_def.get('max_iterations')
            }
        }
        
        # Write to temp file for opendone CLI
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(contract_dict, f)
            contract_path = f.name
        
        try:
            # Call opendone CLI to validate/normalize
            result = subprocess.run(
                ["npx", "opendone", "validate", contract_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                raise RuntimeError(f"OpenDone validation failed: {result.stderr}")
            return contract_dict
        finally:
            Path(contract_path).unlink(missing_ok=True)
    
    def _map_verification_rules(self, outcome_def: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map CapEcon verification rules to OpenDone conditions.
        
        CapEcon has a richer verified_by policy (deterministic_stage, human_confirmation, llm_judge, webhook).
        OpenDone has simpler conditions. This is a lossy mapping for export purposes.
        """
        conditions = {}
        
        # Map CapEcon's verified_by policy to OpenDone conditions
        verified_by = outcome_def.get('verified_by', {})
        for outcome_type, method in verified_by.items():
            if method == 'deterministic_stage':
                conditions[outcome_type] = {'type': 'deterministic'}
            elif method == 'human_confirmation':
                conditions[outcome_type] = {'type': 'manual', 'requires': 'human_review'}
            elif method == 'llm_judge':
                conditions[outcome_type] = {'type': 'automated', 'method': 'llm'}
            elif method == 'webhook':
                conditions[outcome_type] = {'type': 'external', 'method': 'webhook'}
        
        return conditions
    
    def to_opendone_receipt(self, gdr: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export GDR to OpenDone receipt format.
        
        Wraps CapEcon's richer GDR with an OpenDone receipt for external verification.
        This is an EXPORT - CapEcon's internal GDR format remains the primary format.
        
        Args:
            gdr: CapEcon GrowthDecisionRecord dictionary
        
        Returns:
            OpenDone receipt dictionary
        
        Raises:
            RuntimeError: If OpenDone evaluation fails
        """
        # Build input for opendone evaluate
        evaluate_input = {
            'contract': self.to_opendone_contract(gdr.get('outcome_contract', {})),
            'output': gdr.get('outcome', {}),
            'agent': gdr.get('subject', {}).get('agent_id', ''),
            'runtime': {
                'durationMs': gdr.get('runtime_duration_ms'),
                'iterations': gdr.get('iteration_count'),
                'costUsd': gdr.get('economics', {}).get('floor_usd', 0)
            }
        }
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(evaluate_input, f)
            input_path = f.name
        
        try:
            # Call opendone CLI to generate receipt
            result = subprocess.run(
                ["npx", "opendone", "evaluate", input_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                raise RuntimeError(f"OpenDone evaluate failed: {result.stderr}")
            return json.loads(result.stdout)
        finally:
            Path(input_path).unlink(missing_ok=True)
    
    def export_batch(self, gdrs: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """
        Export multiple GDRs to OpenDone receipts.
        
        Args:
            gdrs: List of CapEcon GrowthDecisionRecord dictionaries
        
        Returns:
            List of OpenDone receipt dictionaries
        """
        receipts = []
        for gdr in gdrs:
            try:
                receipt = self.to_opendone_receipt(gdr)
                receipts.append(receipt)
            except RuntimeError as e:
                # Log error but continue with other GDRs
                print(f"Failed to export GDR {gdr.get('record_id', 'unknown')}: {e}")
        return receipts


# CRITICAL: OpenDone is an EXPORT format, not the primary format
# CapEcon's internal GDR format remains unchanged
# CapEcon's Outcome Definition Kit remains the primary format
