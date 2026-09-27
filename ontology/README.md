# CapEcon Ontology

Decision-grade analytics IP for agentic software systems.

## Artifacts (theta recipe)

1. **Taxonomy** — `exception_taxonomy.py`
2. **Semantics** — `*/semantics.yaml` (gloss **and** governing rules)
3. **Schema** — `shared/growth_decision_record.base.schema.json`
4. **Rules evaluator** — `decision_rules.py` (reads YAML → verdict/action)

## Verticals

| Vertical | Role |
| --- | --- |
| `capability_lifecycle` | Ship / throttle / kill capabilities |
| `agent_runtime` | Runtime trust, loops, cost (stricter; destructive → rollback) |
| `orchestration` | Multi-agent handoffs, coordination cost; destructive → kill subgraph (always `requires_review`) |
| `eval_governance` | Eval gate / regression |
| `marketplace_commerce` | Agent-assisted GMV margin at risk |
| `clinical_runtime` | Clinical SDK review labor + residual risk (OpenMed v2.2 case study) |

## Governing decisions from data

Each `semantics.yaml` includes sample policy you can edit without touching Python:

```yaml
classification:
  thresholds:
    capability_harm:
      harm_score_min: 0.08

decision:
  verdict_rules:
    - verdict: destructive
      when_any_category: [capability_harm, trust_break]
    - verdict: leaking
      when_any_category: [activation_leak, habit_collapse]
    # …

  action_map:
    destructive:
      recommended_action: throttle   # agent_runtime uses rollback
      requires_review: true
```

`analytics/decisions.py` loads the profile's vertical at emit time via
`resolve_verdict` / `resolve_action`. Records are schema-validated before return.

Try it: change `agent_runtime` destructive action from `rollback` to `shadow`,
regenerate the workspace, and Radar cards update.

## Validate examples

```bash
python3 -m ontology --examples
```
