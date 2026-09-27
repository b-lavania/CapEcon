# ADP Validation Example

This example demonstrates how to validate CapEcon GDRs against ADP (Agent Decision Protocol) for regulatory compliance.

## Setup

```bash
# Install Node.js from https://nodejs.org/
npm install -g @adp/core

pip install capecon[standards]
```

## Example Code

```python
from standards.adp import ADPValidator

# Initialize ADP validator
try:
    validator = ADPValidator()
    print("ADP validator initialized successfully")
except RuntimeError as e:
    print(f"Failed to initialize ADP validator: {e}")
    print("Please install Node.js and @adp/core: npm install -g @adp/core")
    exit(1)

# Example GDR (replace with your actual GDR)
gdr = {
    'record_id': 'gdr-001',
    'vertical': 'agent_runtime',
    'schema_version': '2.0.0',
    'evaluated_at': '2026-09-26T16:22:48Z',
    'subject': {
        'entity_type': 'capability',
        'capability_id': 'research_agent',
        'agent_id': 'agent-001',
        'agent_type': 'agent',  # Used to infer autonomy level
        'workspace_id': 'my-workspace'
    },
    'exceptions': [],
    'decision': {
        'verdict': 'healthy',
        'recommended_action': 'ship',
        'requires_review': False
    },
    'economics': {
        'floor_usd': 0.50,
        'cap_usd': 10.0
    },
    'evidence': {
        'claim_type': 'associational',
        'n': 100
    }
}

# Add ADP metadata
try:
    enhanced_gdr = validator.add_adp_metadata(gdr.copy())
    print("ADP metadata added successfully")
    
    # Display ADP metadata
    adp = enhanced_gdr['adp']
    print(f"Autonomy Level: {adp['autonomy_level']}")
    print(f"Decision Type: {adp['decision_type']}")
    print(f"Risk Level: {adp['risk_level']}")
    print(f"Classification Code: {adp['classification_code']}")
    print(f"Authorization: {adp['authorization']['result']}")
    print(f"Authorization Reason: {adp['authorization']['reason']}")
    
    # Check if requires_review was overridden
    if enhanced_gdr['decision']['requires_review'] != gdr['decision']['requires_review']:
        print(f"requires_review was overridden by ADP regulatory override")
        print(f"Reason: {enhanced_gdr['decision']['requires_review_reason']}")
        
except RuntimeError as e:
    print(f"Failed to add ADP metadata: {e}")

# Batch validation
gdrs = [gdr]  # Replace with your list of GDRs
try:
    validated_gdrs = validator.validate_batch(gdrs)
    print(f"Validated {len(validated_gdrs)} GDRs against ADP")
except RuntimeError as e:
    print(f"Failed to validate batch: {e}")
```

## Expected Output

```
ADP validator initialized successfully
ADP metadata added successfully
Autonomy Level: A4
Decision Type: operational
Risk Level: low
Classification Code: operational-low
Authorization: auto_approved
Authorization Reason: Autonomy level A4 allows auto-approval for operational decisions
Validated 1 GDRs against ADP
```

## Notes

- ADP validation requires Node.js and @adp/core npm package
- If Node.js is not available, initialization will fail fast with clear error message
- ADP is an OPTIONAL validation layer - CapEcon's triage system remains primary
- ADP can OVERRIDE requires_review for regulatory compliance
- Core CapEcon functionality does not require ADP
