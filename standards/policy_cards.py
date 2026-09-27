"""
Policy Card exporter for CapEcon.

This module exports CapEcon YAML semantics to Policy Card format.
Policy Cards is an optional export format - CapEcon's YAML semantics remain the primary format.

This is a pure Python implementation with local schema validation + external URL reference.

Critical: This is an EXPORT layer, not a replacement for CapEcon's YAML semantics.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import yaml


class PolicyCardExporter:
    """
    Export CapEcon YAML semantics to Policy Card format (pure Python).
    
    Policy Cards is a machine-readable operational constraints format for deployed agents.
    This exporter converts CapEcon's richer YAML semantics to Policy Card JSON format.
    
    This is a pure Python implementation with:
    - Local schema copy for validation
    - External schema URL reference for updates
    
    Requires jsonschema for validation (included in capecon[standards] dependency).
    """
    
    def __init__(self):
        """Initialize Policy Card exporter with local and external schema paths."""
        self.local_schema_path = Path(__file__).parent / 'schemas' / 'policy_card.schema.json'
        self.external_schema_url = "https://raw.githubusercontent.com/OpenAgentGovernance/policy-cards/main/schemas/policy_card.schema.json"
        
        # Ensure local schema directory exists
        self.local_schema_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Download schema if not present
        if not self.local_schema_path.exists():
            self._download_schema()
    
    def _download_schema(self):
        """
        Download Policy Card schema from external URL.
        
        This method downloads the latest schema from the Policy Cards repository
        and saves it locally for validation.
        
        Raises:
            RuntimeError: If download fails
        """
        try:
            import requests
            response = requests.get(self.external_schema_url, timeout=30)
            response.raise_for_status()
            
            with open(self.local_schema_path, 'w') as f:
                json.dump(response.json(), f, indent=2)
                
        except ImportError:
            # If requests is not available, create a minimal schema
            self._create_minimal_schema()
        except Exception as e:
            raise RuntimeError(f"Failed to download Policy Card schema: {e}")
    
    def _create_minimal_schema(self):
        """
        Create a minimal Policy Card schema for validation.
        
        This is a fallback if the external schema cannot be downloaded.
        """
        minimal_schema = {
            "$schema": "http://json-schema.org/draft-2020-12/schema#",
            "type": "object",
            "properties": {
                "policy_id": {"type": "string"},
                "name": {"type": "string"},
                "category": {"type": "string"},
                "rules": {"type": "array"},
                "regulatory_mapping": {"type": "object"},
                "evidence_requirements": {"type": "object"}
            },
            "required": ["policy_id", "name", "category"]
        }
        
        with open(self.local_schema_path, 'w') as f:
            json.dump(minimal_schema, f, indent=2)
    
    def to_policy_card(self, yaml_path: str) -> Dict[str, Any]:
        """
        Export CapEcon semantics.yaml to Policy Card.
        
        Maps CapEcon's richer YAML semantics to Policy Card JSON format.
        This is an EXPORT - CapEcon's YAML semantics with verdict/action maps remains primary.
        
        Args:
            yaml_path: Path to CapEcon semantics.yaml file
        
        Returns:
            Policy Card dictionary
        
        Raises:
            RuntimeError: If YAML parsing or validation fails
        """
        # Load CapEcon semantics
        with open(yaml_path, 'r') as f:
            semantics = yaml.safe_load(f)
        
        # Build Policy Card
        policy_card = {
            '$schema': self.external_schema_url,  # Reference external URL
            'policy_id': f"POL-{semantics.get('vertical', 'unknown').upper()}-001",
            'name': f"{semantics.get('vertical', 'Unknown')} Governance Policy",
            'category': 'operational',
            'rules': self._map_semantics_to_rules(semantics),
            'regulatory_mapping': self._add_regulatory_crosswalk(semantics),
            'evidence_requirements': self._extract_evidence_reqs(semantics)
        }
        
        # Validate against local Policy Card schema
        self._validate_policy_card(policy_card)
        
        return policy_card
    
    def _map_semantics_to_rules(self, semantics: Dict[str, Any]) -> list[Dict[str, Any]]:
        """
        Map CapEcon semantics to Policy Card rules.
        
        CapEcon has a rich rule structure (classification thresholds, verdict rules, action maps).
        Policy Cards has a simpler rule structure. This is a lossy mapping for export.
        
        Args:
            semantics: CapEcon semantics dictionary
        
        Returns:
            List of Policy Card rule dictionaries
        """
        rules = []
        
        # Map classification thresholds to rules
        classification = semantics.get('classification', {})
        thresholds = classification.get('thresholds', {})
        
        for metric, threshold_value in thresholds.items():
            rule = {
                'rule_id': f"threshold_{metric}",
                'type': 'threshold',
                'metric': metric,
                'condition': f'{metric} >= {threshold_value}',
                'action': 'flag'
            }
            rules.append(rule)
        
        # Map verdict rules to rules
        decision = semantics.get('decision', {})
        verdict_rules = decision.get('verdict_rules', [])
        
        for verdict_rule in verdict_rules:
            rule = {
                'rule_id': f"verdict_{verdict_rule.get('verdict', 'unknown')}",
                'type': 'verdict',
                'categories': verdict_rule.get('categories', []),
                'verdict': verdict_rule.get('verdict'),
                'action': verdict_rule.get('action', 'review')
            }
            rules.append(rule)
        
        return rules
    
    def _add_regulatory_crosswalk(self, semantics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add regulatory crosswalk to Policy Card.
        
        This is a placeholder for regulatory mapping. In production, this would
        map CapEcon's semantics to specific regulatory frameworks (EU AI Act, NIST, ISO 42001).
        
        Args:
            semantics: CapEcon semantics dictionary
        
        Returns:
            Regulatory mapping dictionary
        """
        # Placeholder implementation
        return {
            'eu_ai_act': {
                'category': 'unknown',
                'risk_level': 'unknown'
            },
            'nist_ai_rmf': {
                'category': 'unknown',
                'functions': ['govern', 'measure', 'manage']
            },
            'iso_42001': {
                'category': 'unknown',
                'controls': []
            }
        }
    
    def _extract_evidence_reqs(self, semantics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract evidence requirements from semantics.
        
        CapEcon has evidence requirements in the decision structure.
        This maps them to Policy Card evidence requirements.
        
        Args:
            semantics: CapEcon semantics dictionary
        
        Returns:
            Evidence requirements dictionary
        """
        decision = semantics.get('decision', {})
        
        return {
            'min_verified_share': decision.get('min_verified_share', 0.40),
            'requires_experiment_id': decision.get('requires_experiment_id', False),
            'evidence_types': decision.get('evidence_types', ['simulated', 'associational', 'causal'])
        }
    
    def _validate_policy_card(self, policy_card: Dict[str, Any]):
        """
        Validate Policy Card against local JSON Schema (pure Python).
        
        Args:
            policy_card: Policy Card dictionary to validate
        
        Raises:
            RuntimeError: If validation fails
        """
        try:
            import jsonschema
            with open(self.local_schema_path) as f:
                schema = json.load(f)
            jsonschema.validate(instance=policy_card, schema=schema)
        except ImportError:
            # If jsonschema is not available, skip validation
            print("Warning: jsonschema not installed, skipping Policy Card validation")
            print("Install with: pip install capecon[standards]")
        except jsonschema.ValidationError as e:
            raise RuntimeError(f"Policy Card validation failed: {e.message}")
    
    def update_schema(self):
        """
        Update local schema from external URL.
        
        This method downloads the latest schema from the external URL
        and replaces the local copy. Use this to get the latest schema.
        
        Raises:
            RuntimeError: If download fails
        """
        self._download_schema()
    
    def save_to_file(self, policy_card: Dict[str, Any], output_path: str):
        """
        Save Policy Card to a JSON file.
        
        Args:
            policy_card: Policy Card dictionary
            output_path: Path to save the file
        """
        with open(output_path, 'w') as f:
            json.dump(policy_card, f, indent=2)
    
    def export_batch(self, yaml_paths: list[str], output_dir: str):
        """
        Export multiple YAML files to Policy Cards.
        
        Args:
            yaml_paths: List of paths to CapEcon semantics.yaml files
            output_dir: Directory to save Policy Card JSON files
        """
        from pathlib import Path
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for yaml_path in yaml_paths:
            try:
                policy_card = self.to_policy_card(yaml_path)
                yaml_file = Path(yaml_path)
                output_file = output_path / f"{yaml_file.stem}_policy_card.json"
                self.save_to_file(policy_card, str(output_file))
            except Exception as e:
                print(f"Failed to export {yaml_path}: {e}")


# CRITICAL: Policy Cards is an EXPORT format, not the primary format
# CapEcon's YAML semantics with verdict/action maps remains primary
# CapEcon's richer structure (commercial_action_map, thresholds) is preserved
