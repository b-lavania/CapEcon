# Migration Guide: CapEcon v1 → v2.0

## Overview

CapEcon v2.0 adds standards integration (OpenDone, OpenTrajectory, ADP, Policy Cards) and framework adapters (LangGraph, CrewAI, AutoGen, OTel). This migration is **100% backward compatible** - no breaking changes.

## What Changed

### New Features
1. **Pip packaging** - Installable via `pip install capecon`
2. **Standard exporters** - OpenDone, OpenTrajectory, ADP, Policy Cards
3. **Framework adapters** - LangGraph, CrewAI, AutoGen, generic OTel
4. **Standard compliance UI** - 3 new pages in Config section
5. **Optional GDR fields** - `adp`, `opendone_receipt`, `opentrajectory_id` (optional)
6. **Optional YAML sections** - `policy_card_export`, `regulatory_mapping`, `evidence_requirements`

### What's Preserved
- **All proprietary features** - 100% preserved
- **All existing pages** - 44 pages unchanged
- **All existing UI components** - 14 components unchanged
- **All existing adapters** - OTel, Langfuse, Vision unchanged
- **Backward compatibility** - GDR schema v2.0 is backward compatible

## Migration Steps

### For Existing Users

No code changes required. Simply upgrade:

```bash
pip install --upgrade capecon
```

Your existing GDRs will continue to work. Standard fields are optional and default to not present.

### For Developers

If you're using CapEcon as a library:

**Before (v1.x):**
```python
from analytics.decisions import emit_capability_records
from core.workspace import Workspace

ws = Workspace(...)
gdrs = emit_capability_records(ws, ws.profile)
```

**After (v2.0):**
```python
from analytics.decisions import emit_capability_records
from core.workspace import Workspace
from standards.opentrajectory import OpenTrajectoryExporter  # NEW

ws = Workspace(...)
gdrs = emit_capability_records(ws, ws.profile)

# Optional: Export to OpenTrajectory
exporter = OpenTrajectoryExporter()
trajectories = [exporter.to_opentrajectory(gdr) for gdr in gdrs]
```

### For YAML Semantics

Your existing `semantics.yaml` files will continue to work. New optional sections are added:

```yaml
# EXISTING (preserved as-is)
classification:
  thresholds: {...}
decision:
  verdict_rules: [...]
  action_map: {...}

# NEW (optional, v2.0)
policy_card_export:
  enabled: false
  export_format: policy_card
  include_regulatory_crosswalk: true

regulatory_mapping:
  eu_ai_act:
    category: "high_risk"
    risk_level: "high"
  nist_ai_rmf:
    category: "govern"
    functions: ["govern", "measure", "manage"]
  iso_42001:
    category: "aims"
    controls: []

evidence_requirements:
  min_verified_share: 0.40
  requires_experiment_id: false
  evidence_types: ["simulated", "associational", "causal"]
```

### For GDR Schema

GDR schema v2.0 adds optional fields. Existing GDRs without these fields remain valid:

```json
{
  "record_id": "gdr-001",
  "vertical": "agent_runtime",
  "schema_version": "2.0.0",
  "subject": {...},
  "exceptions": [...],
  "decision": {...},
  "economics": {...},
  "evidence": {...},
  "outcome": {...},
  "adp": {                    // NEW (optional)
    "autonomy_level": "A4",
    "decision_type": "operational",
    "risk_level": "medium",
    "classification_code": "operational-medium",
    "authorization": {...}
  },
  "opendone_receipt": {...},   // NEW (optional)
  "opentrajectory_id": "..."    // NEW (optional)
}
```

## Node.js Setup (Optional)

If you want to use OpenDone or ADP export features:

```bash
# Install Node.js from https://nodejs.org/
npm install -g opendone
npm install -g @adp/core
```

If Node.js is not installed, these features will fail fast with clear error messages. Core CapEcon functionality does not require Node.js.

## Testing After Migration

### Verify Existing Functionality

```bash
# Run existing tests
pytest tests/ -m "not slow" --hypothesis-profile=dev

# Run Streamlit app
streamlit run app.py
```

### Verify New Features

```bash
# Test standard exporters
pytest tests/test_standards/ -v

# Test framework adapters
pytest tests/test_integrations/ -v

# Test with optional dependencies
pip install capecon[standards]
python -c "from standards.opendone import OpenDoneExporter"
python -c "from integrations.langgraph import LangGraphAdapter"
```

## Rollback Plan

If you encounter issues, rollback to v1.x:

```bash
pip install capecon==1.0.0
```

All your existing code and data will work with v1.x.

## Support

If you encounter migration issues:
1. Check this guide
2. Review the standards integration documentation
3. Open an issue on GitHub with your error message and environment details
