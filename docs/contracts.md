# What you have to ingest

You do not need the whole `Workspace`. You need the four joins from [methodology.md](methodology.md):

1. AgentRun → Account (via session / end user)
2. AgentRun → Outcome
3. Account → Subscription
4. Account → UsageEvent (what it cost to serve)

Without #1 you have observability. Without #3 you have product analytics. With all four you can talk about retention for an agentic product.

## Tables

| Table | When | Why |
| --- | --- | --- |
| `accounts` | always | Who pays |
| `runs` / `agent_runs` | always | The execution, cost, success, version |
| `spans` | always, metadata only | Steps inside a run. No prompt bodies. |
| `outcomes` | always, or you're guessing | Did the business thing actually happen |
| `subscriptions` | if you want CM-NRR | Revenue |
| `usage_events` | if you want real serving cost | Otherwise we fall back to `run_cost_usd` |
| `approvals` | if there's HITL | Dismiss / confirm |
| `connector_events`, `routing_decisions` | multi-agent / tools | Handoffs, blast radius |
| `eval_results`, `capability_versions` | Version Gate | Eval delta, canary |

Column names follow the empty frames in `core/workspace.py` and the generator. Adapters in `data/adapters/` map other people's exports onto those frames. **Data Connect** is the UI for that.

## What comes out: GrowthDecisionRecord

Schema: [`ontology/shared/growth_decision_record.base.schema.json`](../ontology/shared/growth_decision_record.base.schema.json).

Minimum:

- `subject` — account or capability or seller (`workflow` records still carry a `capability_id` for the source node)
- `exceptions`, `decision` (verdict, recommended_action, requires_review, rule_trace)
- `economics.primary_metric_usd` — cost of leaving live. Teaching formula unless you turned on rigorous mode.
- `evidence.claim_type` — `simulated` | `associational` | `causal`
  - synthetic workspace → `simulated`
  - real ingest, no experiment → `associational`
  - `causal` only with `subject.experiment_id`

Optional write-back on `outcome`: `retention_delta_14d`, `churn_happened`, `actual_run_cost_usd`.

Stored in SQLite via `ontology/store.py`, still appended to JSONL so you can grep it.

## Prompts

I don't want prompt text in this system. Adapters run `data.adapters.scrub.scrub_payload`. There's a test on `tests/fixtures/golden_otel.jsonl` that fails if a content column survives. See methodology §3.4.
