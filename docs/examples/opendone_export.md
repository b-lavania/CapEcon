# OpenDone Export Example

This example demonstrates how to export CapEcon GDRs to OpenDone format for external verification.

## Setup

```bash
# Install Node.js from https://nodejs.org/
npm install -g opendone

pip install capecon[standards]
```

## Example Code

```python
from standards.opendone import OpenDoneExporter

# Initialize OpenDone exporter
try:
    exporter = OpenDoneExporter()
    print("OpenDone exporter initialized successfully")
except RuntimeError as e:
    print(f"Failed to initialize OpenDone exporter: {e}")
    print("Please install Node.js and opendone: npm install -g opendone")
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
    },
    'outcome': {
        'verified_by': 'human_confirmation'
    },
    'outcome_contract': {
        'task': 'Research and summarize documents',
        'outcome_types': ['verified_summary'],
        'verified_by': {
            'verified_summary': 'human_confirmation'
        },
        'max_duration_ms': 30000,
        'max_iterations': 10
    }
}

# Export to OpenDone receipt
try:
    receipt = exporter.to_opendone_receipt(gdr)
    print("OpenDone receipt generated successfully")
    print(f"Receipt passed: {receipt.get('passed', False)}")
    print(f"Criteria results: {len(receipt.get('criteriaResults', []))}")
    print(f"Constraint results: {len(receipt.get('constraintResults', []))}")
except RuntimeError as e:
    print(f"Failed to generate OpenDone receipt: {e}")

# Batch export
gdrs = [gdr]  # Replace with your list of GDRs
try:
    receipts = exporter.export_batch(gdrs)
    print(f"Exported {len(receipts)} GDRs to OpenDone format")
except RuntimeError as e:
    print(f"Failed to export batch: {e}")
```

## Expected Output

```
OpenDone exporter initialized successfully
OpenDone receipt generated successfully
Receipt passed: True
Criteria results: 1
Constraint results: 2
Exported 1 GDRs to OpenDone format
```

## Notes

- OpenDone export requires Node.js and opendone npm package
- If Node.js is not available, initialization will fail fast with clear error message
- OpenDone is an EXPORT format - CapEcon's internal GDR format remains the primary format
- Core CapEcon functionality does not require OpenDone
