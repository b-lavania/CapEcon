# LangGraph + CapEcon Example

This example demonstrates how to integrate CapEcon with LangGraph to generate GDRs from LangGraph traces.

## Setup

```bash
pip install capecon[standards]
pip install langgraph
```

## Example Code

```python
from integrations.langgraph import LangGraphAdapter
from standards.opentrajectory import OpenTrajectoryExporter

# Initialize LangGraph adapter
adapter = LangGraphAdapter()

# Example LangGraph trace (replace with your actual trace)
langgraph_trace = {
    'workspace_id': 'my-workspace',
    'node_executions': [
        {
            'node_id': 'node-001',
            'node_name': 'research_agent',
            'agent_id': 'agent-001',
            'cost_usd': 0.50,
            'budget_cap': 10.0,
            'error': None,
            'retry_count': 0
        },
        {
            'node_id': 'node-002',
            'node_name': 'writer_agent',
            'agent_id': 'agent-002',
            'cost_usd': 0.75,
            'budget_cap': 10.0,
            'error': None,
            'retry_count': 1
        }
    ]
}

# Ingest trace and generate GDRs
gdrs = adapter.ingest_langgraph_trace(langgraph_trace)

print(f"Generated {len(gdrs)} GDRs from LangGraph trace")

# Display GDRs
for gdr in gdrs:
    print(f"GDR: {gdr['record_id']}")
    print(f"  Capability: {gdr['subject']['capability_id']}")
    print(f"  Verdict: {gdr['decision']['verdict']}")
    print(f"  Action: {gdr['decision']['recommended_action']}")
    print(f"  Floor: ${gdr['economics']['floor_usd']:.2f}")
    print()

# Optional: Export to OpenTrajectory
exporter = OpenTrajectoryExporter()
trajectories = [exporter.to_opentrajectory(gdr) for gdr in gdrs]

print(f"Exported {len(trajectories)} trajectories to OpenTrajectory format")
```

## Integrating with LangGraph State

```python
from langgraph.graph import StateGraph
from integrations.langgraph import LangGraphAdapter

# Initialize adapter
adapter = LangGraphAdapter()

# Define your LangGraph graph
graph = StateGraph()

# ... define your nodes and edges ...

# Capture trace during execution
trace = {
    'workspace_id': 'my-workspace',
    'node_executions': []
}

# After execution, ingest trace
gdrs = adapter.ingest_langgraph_trace(trace)
```

## Expected Output

```
Generated 2 GDRs from LangGraph trace
GDR: langgraph-node-001-2026-09-26T16:22:48.123456
  Capability: research_agent
  Verdict: healthy
  Action: ship
  Floor: $0.50

GDR: langgraph-node-002-2026-09-26T16:22:48.234567
  Capability: writer_agent
  Verdict: healthy
  Action: ship
  Floor: $0.75

Exported 2 trajectories to OpenTrajectory format
```

## Notes

- LangGraph adapter is NEW in v2.0 and does NOT replace existing OTel/Langfuse adapters
- GDRs are generated from LangGraph node executions
- OpenTrajectory export is optional
- Existing CapEcon proprietary features (price block, commercial actions, triage, etc.) are preserved
