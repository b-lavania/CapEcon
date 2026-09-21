# Naming a verified outcome

If you can't say what success looks like, the rest of this repo is a dashboard of runs. Traces without outcomes are observability. "The LLM said it worked" is not verification.

**Setup → Outcome Definition** is the wizard. The contract itself is `ontology/outcome_contract.py`.

## Fields I actually need

| Field | Notes |
| --- | --- |
| `outcome_id` | PK |
| `agent_run_id` | which run |
| `account_id` | who pays |
| `outcome_type` | your enum, not mine |
| `success` | bool |
| `verified` | bool |
| `verified_by` | see below |
| `verified_at` | timestamp |
| `outcome_value_usd` | optional |

## `verified_by`

- `deterministic_stage` — schema check, rate engine, graph completion. Best.
- `human_confirmation` — a person or a downstream click.
- `llm_judge` — allowed, labeled weaker. Never treat it as ground truth quietly.
- `webhook` — some other system said it happened.

## Examples (templates, not product types)

| Shape | Example types | I'd verify with |
| --- | --- | --- |
| Quote / ops | quote_sent, quote_accepted, booking_created | deterministic_stage or a human |
| Support | issue_resolved, escalated, csat_logged | human + survey if you have it |
| Analyst | report_generated, query_accepted, reused | someone actually used the output; judge is a last resort |
| Orchestrator | task_completed, sla_met, no_extra_hitl | the graph finished |

Activation for these products is **first verified autonomous outcome**, not first login. That's `activation_verified_14d` / `time_to_first_value` in the lexicon.

## When I call it "ready"

There's at least one `outcome_type` in the session contract, the `outcomes` table isn't empty, and enough rows are `verified` with a known `verified_by` (default floor 40%). If that fails, the honest next step is instrumentation, not Version Gate.
