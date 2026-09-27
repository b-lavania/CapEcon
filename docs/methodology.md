# The Agentic Retention System: Detailed Build Plan

> **Demo honesty:** CapEcon ships synthetic data and teaching formulas. For what is simulated vs associational vs causal, see [`honesty.md`](honesty.md). The app's Version Gate / Data Connect / Outcome Definition pages are the short version of this writeup. Longer argument in [`positioning.md`](positioning.md).

## Part 1 — The Problem, Grounded in Data

Before the data model, you need to understand why this problem is structurally different from SaaS churn and why the window is opening now.

**Most agentic products never reach production.** 80% of enterprise apps embed an AI agent but only 31% run one in production, and 88% of pilots never ship.^1^ This means most of your friends' companies are probably pre-production — verify this before assuming they have retention data to analyze. If they're in pilot, the system you build is about *deployment success prediction*, not churn prevention. Different product.

**For those that do ship, there's a 37% performance gap from lab to production.^2^** Agents that scored well in testing degrade in production due to real-world data variance, tool failures, and context drift. This degradation is the silent churn driver — the agent gets worse over time, users notice before the company does, and they leave. Traditional analytics sees the login frequency drop but not *why*. Only trace-level outcome data captures the degradation.

**Cost of serving is badly underestimated.** Infrastructure costs are 3–5x higher than initial LLM API cost estimates.^3^ The median enterprise monthly LLM bill grew 7.2x year-over-year entering Q1 2026.^4^ This means a retained account with heavy usage can be margin-negative without anyone noticing — the revenue looks fine in Stripe, the cost is buried across multiple inference providers and tool calls. Your contribution-margin NRR metric isn't a nice-to-have; it's the number that prevents your friends from scaling themselves into bankruptcy.

**The evaluation gap is the #1 cited failure factor.** Only 10% of enterprises successfully implement generative AI in production, with inadequate evaluation frameworks cited as the main failure factor.^2^ Deloitte's 2025 AI ROI research confirms that 85% of AI ROI leaders use distinct frameworks for generative versus agentic AI.^5^ This is your opening: there is no standard framework, and the people who should have one don't.

**Governance is centralizing.** 56% of enterprises now name a dedicated 'AI agent owner' or 'agentic ops' lead in 2026, up from 11% in 2024.^4^ This is your buyer if you productize — not the PM, not eng, but the person whose job title didn't exist 18 months ago and who is desperate for metrics that justify their role.

---

## Part 2 — Why Existing Tools Fail for This Problem

| Tool category | What they capture | What they miss for retention |
|---|---|---|
| Langfuse / LangSmith / Helicone | Traces, spans, LLM calls, token cost, evals | No account/subscription linkage, no revenue data, no churn signal |
| Amplitude / PostHog / Mixpanel | User events, sessions, funnels, retention cohorts | No agent internals, no outcome quality, no cost-per-outcome |
| Stripe / Metronome / Orb | Revenue, usage metering, billing | No agent behavior, no outcome success, no quality signal |
| ChartMugul / ChurnZero / ProfitWell | MRR/NRR, churn cohorts, health scores | No agent data at all — health scores are proxies built on login/usage |

The gap is the **join**. Nobody links trace-level agent outcomes to account-level revenue and retention. That join is the product.

---

## Part 3 — The Data Model (Detailed)

This is the core IP. Not the dashboard, not the alerts — the data model that makes the joins possible. I'll use your Quotely freight quoting agent as the concrete example throughout, because you know it cold.

### 3.1 Entity Relationship Overview

```
Account ──< EndUser ──< Session ──< AgentRun ──< Span
   │                                         │
   │                                         └──> Outcome
   │
   └──< Subscription ──< Invoice ──< UsageEvent
```

### 3.2 Core Entities

**Account** — the paying customer organization.

| Field | Type | Notes |
|---|---|---|
| account_id | string (PK) | From your CRM or Stripe customer ID |
| name | string | |
| tier | enum | `pilot`, `self_serve`, `mid_market`, `enterprise` — this is your #1 retention segmentation variable |
| pricing_model | enum | `seat_based`, `usage_based`, `outcome_based`, `hybrid` — determines how you read NRR |
| industry_vertical | string | For benchmarking across your friend group |
| created_at | timestamp | Account creation, not first usage |
| onboarding_completed | bool | Whether they completed setup — your first activation gate |

**EndUser** — the human interacting with the agent.

| Field | Type | Notes |
|---|---|---|
| end_user_id | string (PK) | |
| account_id | string (FK) | |
| role | string | dispatcher, shipper, ops_manager — role determines delegation patterns |
| created_at | timestamp | |
| last_active_at | timestamp | Updated by session events |

**Session** — a contiguous interaction window.

| Field | Type | Notes |
|---|---|---|
| session_id | string (PK) | |
| end_user_id | string (FK) | |
| channel | enum | `sms`, `web`, `api`, `voice` — Vapi-based products use `voice` |
| started_at | timestamp | |
| ended_at | timestamp | Nullable; closed when session times out |
| agent_runs_count | int | Denormalized for quick filtering |

**AgentRun** — a single goal-directed agent execution. This is the central entity. One session may contain multiple agent runs (e.g., user asks for three quotes in one SMS conversation).

| Field | Type | Notes |
|---|---|---|
| agent_run_id | string (PK) | |
| session_id | string (FK) | |
| agent_version | string | Hash or semantic version of prompt + model + tools config — critical for drift detection |
| goal | string | `generate_quote`, `check_availability`, `create_booking` — the deterministic pipeline stage this run serves |
| started_at | timestamp | |
| completed_at | timestamp | Nullable; null means timeout or still running |
| status | enum | `success`, `failure`, `escalated`, `timeout`, `cancelled` |
| hitl_triggered | bool | Whether human review was invoked |
| hitl_reason | string | `low_confidence`, `explicit_request`, `policy_violation`, `schema_validation_failed` — your Cohen's Kappa threshold triggers go here |
| total_input_tokens | int | Sum across all LLM calls in this run |
| total_output_tokens | int | |
| total_cost_usd | decimal | Sum of all span costs — this is your variable cost of serving |
| total_latency_ms | int | End-to-end wall time |
| span_count | int | Number of steps — proxy for loop iterations |
| outcome_id | string (FK) | Nullable; links to the Outcome entity if one was produced |

**Span** — individual steps within an agent run. This is where observability tools already operate; you're ingesting their data, not replacing them.

| Field | Type | Notes |
|---|---|---|
| span_id | string (PK) | |
| agent_run_id | string (FK) | |
| parent_span_id | string (FK) | Nullable; for nested agent calls |
| span_type | enum | `llm_call`, `tool_call`, `retrieval`, `deterministic_stage`, `human_review`, `guardrail_check` |
| name | string | e.g., `rag_retrieve_rates`, `llm_generate_quote_text`, `validate_quote_schema` |
| started_at | timestamp | |
| completed_at | timestamp | |
| input_tokens | int | LLM calls only |
| output_tokens | int | LLM calls only |
| cost_usd | decimal | |
| status | enum | `success`, `error`, `retry`, `skipped` |
| metadata | jsonb | Tool-specific data: retrieval scores, function call args, validation errors |

**Outcome** — the business result. This is the entity that doesn't exist in any observability tool and is the entire reason this data model has value.

| Field | Type | Notes |
|---|---|---|
| outcome_id | string (PK) | |
| agent_run_id | string (FK) | |
| outcome_type | enum | Product-specific. For Quotely: `quote_sent`, `quote_accepted`, `quote_rejected`, `booking_created`, `dispatch_confirmed`. For a Vapi voice agent: `call_completed`, `booking_made`, `issue_resolved`, `call_transferred`. For a Lindy workflow: `task_completed`, `task_failed`, `task_escalated` |
| outcome_value_usd | decimal | Nullable; monetary value if applicable (e.g., freight quote dollar amount) |
| verified_by | enum | `deterministic_stage`, `human_confirmation`, `llm_judge` — this is critical: deterministic pipeline stages provide ground-truth labels that pure-LLM observability can't auto-compute |
| verified_at | timestamp | |
| created_at | timestamp | |

**Subscription** — from Stripe or equivalent.

| Field | Type | Notes |
|---|---|---|
| subscription_id | string (PK) | |
| account_id | string (FK) | |
| status | enum | `active`, `past_due`, `canceled`, `trialing` |
| plan_id | string | |
| pricing_model | enum | Mirrors account-level for denormalization |
| started_at | timestamp | |
| churned_at | timestamp | Nullable |
| churn_reason | string | Nullable; populated from exit survey or CS notes |

**UsageEvent** — metered usage for billing. If using Metronome/Orb, this comes from their API.

| Field | Type | Notes |
|---|---|---|
| usage_event_id | string (PK) | |
| account_id | string (FK) | |
| subscription_id | string (FK) | |
| timestamp | timestamp | |
| event_type | enum | `agent_run`, `llm_call`, `tool_call`, `outcome_success` |
| quantity | decimal | |
| unit_cost_usd | decimal | |
| total_cost_usd | decimal | |

### 3.3 The Critical Joins

These four joins are the entire product. Every metric flows from them.

1. **AgentRun → Account** (via Session → EndUser → Account): Enables per-account outcome success rates, cost-per-outcome, autonomy ratios.
2. **AgentRun → Outcome**: Enables outcome success rate by agent version, by account, by time period.
3. **Account → Subscription**: Enables revenue alongside agent behavior — contribution margin per account.
4. **Account → UsageEvent**: Enables actual cost of serving alongside revenue — the margin killer detector.

Without join #1, you have observability. Without join #3, you have product analytics. With all four, you have retention analytics for agentic products.

### 3.4 What This Data Model Does NOT Include (and Why)

- **No raw prompt/response storage in the core model.** Prompts contain PII and business logic. Store them in Langfuse/LangSmith; reference by trace_id. Your system should work with metadata only. This matters for security reviews — if you can demonstrate you don't store prompt content, VPC deployment becomes less critical.
- **No real-time streaming.** Batch ingestion from existing tools via their export APIs. Real-time is a Phase 3+ concern; retention analysis works on daily/weekly cadences.
- **No user interface events (clicks, page views).** If you need them, pull from PostHog/Amplitude by session_id. Don't replicate their data.

---

## Part 4 — The Metric Framework

### 4.1 Activation (Not What You Think)

Traditional SaaS activation: first meaningful action within X days. Wrong for agentic products.

**Agentic activation:** First *verified autonomous outcome* within X days of account creation.

For Quotely: the first quote generated by the agent that was either accepted by the customer or verified by the deterministic rate engine — not the first login, not the first SMS sent, not the first agent run attempted.

Why this matters: accounts that interact with the agent but never get a successful outcome are tourists. They churn at 80%+ rates. Accounts that get a successful outcome in week 1 retain at 2-3x the rate of those who don't. This is testable with your friends' data immediately.

**Required evidence to validate:** Pull your friends' data. Cohort accounts by "days to first verified outcome." Plot retention at 30/60/90 days. If the curve doesn't diverge sharply, this metric is wrong for their product.

### 4.2 The Core Retention Metrics

**Delegation Ratio** — percent of eligible tasks delegated to the agent vs. done manually, per account, per week.

In your Quotely context: of all freight quotes requested by this account last week, what percentage went through the agent vs. were handled by a human dispatcher? A declining delegation ratio is the earliest churn signal — the user is silently losing trust in the agent and reverting to manual processes. They haven't churned yet, but they will.

This metric inverts traditional product analytics. In SaaS, more user activity = engagement. In agentic products, more user activity in the agent's domain = the agent is failing and the human is doing the work. Your friends are probably tracking "active users" and celebrating when it goes up. It should be alarming.

**Autonomy Ratio** — agent-resolved outcomes / total outcomes (including HITL escalations), per account, per week.

Your Cohen's Kappa threshold triggers HITL escalation. If an account's autonomy ratio drops from 85% to 60% over four weeks, either their use cases got harder (they're pushing the agent into edge cases — actually a good sign, they're finding value) or the agent is degrading (model update, retrieval quality drop — a bad sign). You need to distinguish these, which requires segmenting by outcome type and agent version.

**Cost per Successful Outcome** — total_cost_usd across all agent runs for an account / count of successful outcomes for that account.

This is the margin metric. If your friends are pricing per quote but it costs $0.80 in inference to generate a quote that succeeds and $2.40 per quote that fails (because of retries, loop iterations, HITL overhead), they need to know which accounts have the worst ratio. High-cost-per-outcome accounts are either candidates for pricing increases or candidates for churn — and the data tells you which.

**Contribution-Margin NRR** — (revenue retained from account cohort) - (inference + tooling cost for that cohort) / (original revenue from that cohort), measured at month 12.

Traditional NRR ignores cost of serving. In seat-based SaaS, this is fine — marginal cost is near zero. In agentic products, cost of serving is variable and grows with usage. An account that expands usage 3x but costs 5x more to serve has negative contribution-margin NRR even though traditional NRR looks like 300%. This is the number that determines whether your friends' businesses are viable at scale.

**Outcome Success Drift** — success rate for the same outcome type, same agent version, same account cohort, compared week-over-week.

The 37% lab-to-production performance gap means agents degrade in ways that don't show up in error rates.^2^ The agent doesn't crash; it just produces worse quotes. The user doesn't complain; they just stop using the product. Outcome success drift catches this before the user notices.

### 4.3 The Churn Taxonomy

Every churned account gets a reason code. No exceptions. Without this, you're counting bodies, not preventing deaths.

| Reason code | Definition | Leading indicator | Intervention |
|---|---|---|---|
| `tourist` | Never achieved first verified outcome | No outcome within 14 days of signup | Onboarding intervention or disqualify the segment |
| `value_failure` | Achieved outcomes initially, success rate declined over time | Outcome success drift, declining delegation ratio | Agent quality investigation, model/prompt rollback |
| `efficiency` | Agent works but user finds manual process faster | Declining delegation ratio with stable success rate | Workflow redesign, not agent improvement |
| `displacement` | Customer built in-house replacement | Sudden delegation ratio drop to near zero, new integration patterns | Competitive intelligence, likely unpreventable |
| `price` | Churned after pricing change or usage-based bill shock | High cost-per-outcome relative to perceived value | Pricing tier adjustment, usage caps |
| `champion_departure` | Internal advocate left the company | Account-level contact change | Re-onboarding with new contact |
| `product_gap` | Agent couldn't handle their use case | High HITL escalation rate from start, feature requests logged | Product roadmap input, may be unpreventable |

---

## Part 5 — Instrumentation Requirements

The search results validate what the system needs at the infrastructure level:

**Logging pipeline requirements:** Every agent invocation logs input, output, tool calls, latency, token usage, and errors. Store logs in a queryable format (structured JSON to a data warehouse). Retention: minimum 90 days for debugging, 1 year for trend analysis.^6^

**Instrumentation at every decision point:** Using tools like OpenTelemetry, detailed logging is performed at each agent decision point to capture task success, tool interactions, and LLM reasoning.^7^

**What this means for your friends:** If they're using Langfuse or LangSmith, they already have spans and traces. If they're not instrumenting at all, Phase 0 includes getting them on Langfuse (open-source, self-hostable) — because without traces, the data model has no Span table to populate, and without Span data, you can't compute cost-per-outcome or detect drift.

**The OpenTelemetry bet:** OpenTelemetry GenAI semantic conventions (`gen_ai.*` attributes) are the emerging standard for LLM observability. If your friends emit OTel-compatible traces, your ingestion layer is framework-agnostic. If they're locked into LangChain-specific instrumentation, you're rebuilding every time they switch frameworks. Push them toward OTel.

---

## Part 6 — Implementation Plan (Revised with Data Model)

### Phase 0 — Inventory & Feasibility (3 weeks)

For each friend (target: 3–5 companies):
1. Are they in production or pilot? If pilot, they have no retention data. Park them.
2. How many paying accounts? Need ≥50 for statistical signal. Below that, you're doing case studies, not analytics.
3. What observability tool do they use? If none, they need Langfuse first. That's a prerequisite, not your problem to solve but a gate.
4. What are their outcome types? Get the actual list. If they can't define outcomes, they can't measure retention — this is itself a finding worth delivering.
5. What's their pricing model? Usage-based companies need contribution-margin NRR. Seat-based companies can start with traditional NRR plus agent quality.

**Kill criterion:** Fewer than 2 friends with ≥50 paying accounts, production deployment, existing trace instrumentation, and definable outcomes. If that's the case, the system is premature — build the metric dictionary and wait for the market to mature.

### Phase 1 — The Metric Dictionary + Data Model Implementation (4–6 weeks)

For 2–3 qualifying friends:

1. **Implement the data model** as dbt models on their warehouse (or spreadsheets if no warehouse). Source tables:
   - Langfuse/LangSmith export → populates AgentRun, Span
   - Stripe export → populates Subscription, Invoice
   - Their application DB → populates Account, EndUser, Session, Outcome

2. **Define outcomes** for each friend. This is product-specific consulting work. For Quotely: `quote_sent` (agent generated and sent a quote), `quote_accepted` (customer accepted the quote — this is your deterministic ground truth), `quote_rejected` (customer rejected), `escalated_to_human` (HITL triggered). For a Vapi voice agent friend: `call_completed` (call ended normally), `booking_made` (agent successfully booked something during the call), `issue_resolved` (caller confirmed resolution), `call_transferred` (agent escalated to human).

3. **Compute the five core metrics** for the last 90 days of their data:
   - Activation rate (first verified outcome within 14 days)
   - Delegation ratio by week
   - Autonomy ratio by week
   - Cost per successful outcome by account
   - Contribution-margin NRR for the current cohort

4. **Deliverable:** A weekly account health report per friend. Each account scored on delegation ratio trend, autonomy ratio trend, cost-per-outcome, and outcome success drift. Plus a churn risk list with reason codes.

**Kill criterion:** If after 6 weeks, fewer than 2 stakeholders per friend check the report weekly, the metrics aren't decision-driving. Either the metrics are wrong or the pain isn't real. Both are fatal for productization.

### Phase 2 — The Intervention Loop (4 weeks)

Dashboards don't prevent churn; interventions do. This phase adds:

1. **Alerting rules:**
   - Delegation ratio drops >15% week-over-week → alert account owner
   - Autonomy ratio drops >10% over 4 weeks → alert eng (possible agent degradation)
   - Cost-per-outcome exceeds account's pricing margin → alert finance/PM
   - No successful outcome in 14 days for an active account → alert CS

2. **Playbooks per churn taxonomy category** (see Part 4.3). Each alert links to a specific playbook with steps, owner, and expected outcome.

3. **Weekly review cadence:** 30-minute meeting per friend to review flagged accounts, assign interventions, and track outcomes of prior interventions.

**Validation:** Were flagged accounts touched within a week? Did flagged accounts churn at a lower rate than unflagged controls? If you can't show this delta, the system has no proven value.

### Phase 3 — Productization Decision (week 12)

At this point you have:
- A validated data model working across 2–3 companies
- A metric dictionary that generalizes (or doesn't — this is the key finding)
- Evidence of whether interventions triggered by the metrics actually reduce churn
- Cross-company benchmark data (anonymized) — this is the asset that ChartMogul leveraged to build authority

**Decision tree:**
- Metrics generalized + interventions worked → productize as the outcome-translation layer. Target buyer: the "agentic ops lead" that 56% of enterprises now have.^4^
- Metrics generalized + interventions didn't work → you have a diagnostic tool, not a retention tool. Pivot to evaluation/monitoring positioning.
- Metrics didn't generalize → you have a consulting practice. This is legitimate and profitable, and may be the better business given your retention expertise.

---

## Part 7 — What I'm Not Sure About (Flagged Unverified)

1. **Whether delegation ratio is universally meaningful.** It's clearly meaningful for your Quotely freight agent (humans can do the task manually). It may not be meaningful for a Vapi voice agent (there's no manual alternative — you either take the call or you don't). For voice agents, the equivalent might be "call deflection rate" (agent resolved without human transfer). Required evidence: test with your Vapi-ecosystem friend.

2. **Whether outcome definitions will generalize across verticals.** A freight quote outcome and a customer support resolution outcome are structurally different. The data model accommodates this (outcome_type is product-specific), but the *metrics built on outcomes* may not transfer. Required evidence: complete Phase 1 for at least 2 non-similar products and compare.

3. **Whether 50 accounts is the right threshold.** It's a guess based on needing ~20 churn events for statistical signal at a 40% GRR. If your friends have higher churn (60%+), 30 accounts may suffice. If lower, you need 100+. Required evidence: actual account counts and churn rates from Phase 0.

4. **Whether the contribution-margin NRR metric is computable from available data.** It requires cost-per-agent-run, which requires token-level cost tracking. If your friends use OpenAI/Anthropic directly, this is available. If they use a gateway (LiteLLM, Portkey), the gateway has it. If they use a managed platform (Vapi, Lindy), the platform may not expose per-call cost. Required evidence: check each friend's cost data availability in Phase 0.

---

## The Bottom Line

The data model is the product. Specifically: the four joins that link agent behavior to account revenue to churn outcomes. Everything else — the metrics, the dashboards, the alerts — flows from those joins. If you get the data model right, the metrics are SQL queries. If you get it wrong, no amount of dashboard polish will save you.

Start with Phase 0 this week. Call your friends. Ask: are you in production, how many paying accounts, what observability tool, and can you define your outcomes in one sentence. The answers determine whether this is a 3-month project or a 12-month one.

7 Citations

Enterprise AI Agents Adoption Statistics 2026 - Paul Okhrem
https://paul-okhrem.com/enterprise-ai-agents-statistics-2026/

Beyond Accuracy: A Multi-Dimensional Framework for Evaluating Enterprise Agentic AI Systems
https://arxiv.org/html/2511.14136v1

Agentic AI Statistics 2026: 150+ Data Points Collection
https://www.digitalapplied.com/blog/agentic-ai-statistics-2026-definitive-collection-150-data-points

AI Agent Adoption 2026: 120+ Enterprise Data Points
https://www.digitalapplied.com/blog/ai-agent-adoption-2026-enterprise-data-points

Benchmarking Agentic AI Performance: ROI & KPIs Guide
https://www.cygnet.one/feeds/blog/benchmarking-performance-roi-agentic-ai-implementations

AI Agent Evaluation in Production (2026 Guide)
https://thinking.inc/en/blue-ocean/agentic/ai-agent-evaluation-production/

Evaluating Agentic AI in the Enterprise: Metrics, KPIs, and Benchmarks - auxiliobits
https://www.auxiliobits.com/blog/evaluating-agentic-ai-in-the-enterprise-metrics-kpis-and-benchmarks/