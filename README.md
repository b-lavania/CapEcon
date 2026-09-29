# CapEcon

Figuring out how agentic products should handle churn, retention, and monetization, and what it actually costs to leave a capability live.

---

## How this started

The first version of this was a bunch of spreadsheets. Retention curves, churn cohort breakdowns, attribution models for a couple of marketplaces and ecomm stores I was studying. I was trying to answer the same question everyone asks: *why are people leaving, and what can we actually do about it?*

Those spreadsheets turned into a Python project. I built out a causal waterfall, survival models, experimentation scaffolding, even a full Bayesian MMM pipeline with PyMC. It worked, in the sense that the math was sound, but it was still fundamentally about customers and transactions. Traditional SaaS/ecomm retention.

Then I started paying attention to agentic products (AI assistants, CRM copilots, ops agents) and realized the retention problem is completely different there: you're not retaining customers in the old sense, instead you're shipping features (skills, automations, agent tools).

So the question becomes: is this capability helping or hurting? Is it worth the inference cost? Should we throttle it, roll it back, or kill it entirely? The old spreadsheet models didn't have a place for that; I rebuilt the whole thing around capabilities instead of customers and that's ***CapEcon***.

The follow-on question, once you have more than one agent in production, is even less pretty: did this *version* make things better or worse, and can you tell before the customer does? That's what **Version Gate** is for. I still don't want this repo to be another agent runtime. There are already too many of those.

---

## What it actually does

You pick a product profile (what kind of agentic product are you?), generate a synthetic warehouse of seats, capabilities, agent runs, approvals, and connectors, or overlay a real OTel/Langfuse export plus CSVs on **Data Connect**, and then the engine classifies exceptions, prices the cost of leaving things as they are, and emits a ranked **GrowthDecisionRecord**.

The GDR is not an ops alert dressed up as analytics. It's supposed to be a **priceable, honest unit of account**: floor, cap, risk, `cost_basis`, `claim_type`, and (when the dialect allows) list or take. Radar still sorts on `primary_metric_usd`, the headline rollup. The unit cost of producing one verified outcome lives in `floor_usd` beside it. I did not merge those on purpose.

```text
Profile (ontology switch)  /  Data Connect (optional overlay)
   > Warehouse (seats, capabilities, runs, approvals, connectors, outcomes)
   > Classify (exceptions from thresholds)
   > YAML rules (verdict → recommended action)     < edit policy here
   > Price block (floor / cap / dialect sentence)
   > GrowthDecisionRecord
   > Version Gate / Radar / Decision Inbox
   > Outcome Flywheel (write-back onto the same record)
```

The loop, step by step:

1. **Profile**: Pick a preset (`assistant_heavy`, `workspace_crm`, `ops_mission`, `marketplace_agentic`, `openmed_v22`, etc.). That switches the ontology vertical, the synthetic priors, and the default `pricing_mode`. If you have files, **Data Connect** first.
2. **Outcomes**: If you can't name what "verified success" means, stop and use **Outcome Definition**. Login is not an outcome.
3. **Generate / overlay**: Build the warehouse. Synthetic by default.
4. **Version Gate**: Should this capability version ship, hold, or roll back? Eval delta, canary SPRT, then a GDR you can drop in the Inbox. Same logic is on `POST /version-gate` if you want a CI check.
5. **Radar / Inbox**: Rank by headline `primary_metric_usd`. Read the price sentence on the card for floor vs cap. Override if you disagree. Inbox is the same records with a triage state.
6. **Close loop**: Outcome Flywheel writes `retention_delta` and `churn_happened` back onto the same record.

---

## The unit of account (not just a verdict)

I got tired of dashboards that say "cost blew out" without saying whether that's a routing bug, a SKU problem, or a packaging ask. So every emitter now calls `fill_price_block()` in `analytics/price_block.py`.

Three **pricing dialects**, no global default. The preset picks:

| Dialect | Who it's for | What shows on the card |
| --- | --- | --- |
| `internal_budget` | Internal agents (assistants, ops, clinical) | Floor vs budget cap vs human baseline. **No `list_usd`.** |
| `product_sku` | Metered API products | Floor vs cap vs implied list |
| `marketplace_take` | Platform take-rate | Floor vs implied take |

**`cost_basis`** is per-row, and aggregates take the weakest link: `simulated < estimated < allocated < metered`. A GDR covering 1,240 runs where 300 are still token-oracle estimates must not badge itself `metered` because one row had an invoice.

**Ops vs commercial** are separate axes on the same decision. `recommended_action` is runtime (`ship`, `hold`, `throttle`, `rollback`). `commercial_action` is packaging (`raise_list`, `split_tier`, `reallocate`, …). YAML picks the verb; Python computes the signal. A cheaper model holding the eval band should surface `reallocate` before anyone asks finance to raise a list price.

Clinical (`openmed_v22`) splits **floor** (inference + review labor per run) from **risk** (expected harm). The Radar headline stays the window total so sort order doesn't jump around.

What's still honest about limits: [`docs/slice2_build_audit.md`](docs/slice2_build_audit.md) lists what shipped in phases 0-A and what's deliberately not built yet (Version Gate commercial CI payload, meter export, theta spine merge, etc.).

---

## The join

LangGraph runs the loop. Langfuse stores traces. Stripe invoices.

What's missing is the join: **traces × verified outcomes × trust × what it cost to serve**. Without account linkage you have observability. Without subscriptions you have product analytics. With all four you can talk about retention *and* unit economics for an agentic product. [`docs/contracts.md`](docs/contracts.md) is the table-level spec.

I don't want prompt text in this system. Adapters scrub content keys; `tests/fixtures/golden_otel.jsonl` fails the build if a prompt column survives ingest.

## Related work (simulators vs CapEcon)

These projects **simulate** markets, macro agents, RL economies, or ABMs. CapEcon **prices and decides** after you export a file and overlay it on Data Connect. See [`docs/adapters.md`](docs/adapters.md).

| Repository | Role relative to CapEcon |
| --- | --- |
| [microsoft/multi-agent-marketplace](https://github.com/microsoft/multi-agent-marketplace) | Market experiment exports → `market` adapter |
| [marketagents-ai/MarketAgents](https://github.com/marketagents-ai/MarketAgents) | Double-auction / coordination exports → `market` |
| [tsinghua-fib-lab/ACL24-EconAgent](https://github.com/tsinghua-fib-lab/ACL24-EconAgent) | Macro period aggregates → `macro` |
| [sethkarten/LLM-Economist](https://github.com/sethkarten/LLM-Economist) | Mechanism / policy sims → `macro` |
| [FreedomIntelligence/TwinMarket](https://github.com/FreedomIntelligence/TwinMarket) | Financial blotter shape → `finance` |
| [ponseko/econojax](https://github.com/ponseko/econojax) | RL episode logs → `rl` |
| [econ-ark/HARK](https://github.com/econ-ark/HARK) | Heterogeneous-agent scenarios → `abm` |
| [scikit-agent/scikit-agent](https://github.com/scikit-agent/scikit-agent) | ABM / MAS toolkit → `abm` |
| [salesforce/ai-economist](https://github.com/salesforce/ai-economist) | Two-level RL policy sims → `rl` |
| [FreedomIntelligence/Awesome-Econ-World-Models](https://github.com/FreedomIntelligence/Awesome-Econ-World-Models) | Discovery index only |

CapEcon does not vendor or run those repos.

---

## Data Connect, including Vision (two records)

**Data Connect** is where real files land: OTel JSONL, Langfuse export, LangGraph node dumps, market experiment JSONL, CSVs for accounts/outcomes/subscriptions/usage, Vision Agent pack, and (under More sim exports) RL / macro / ABM / finance fixtures.

That last one matters because it's the first non-synthetic path where agent API cost and customer invoice are both real numbers. Putting them on one GDR is a category error:

| Source | Field | Record | Basis |
| --- | --- | --- | --- |
| Bakeoff `run.json` | `model_summaries.*.cost_usd` | **agent GDR** `floor_usd` | `estimated` (token oracle) |
| Historic jobs JSONL | `actuals.price_dollars` | **move quote** `charged_usd` | `invoiced` if `actuals_quality=trusted`, else `reconstructed` |

The adapter is `data/adapters/vision.py`. Fixtures live in `tests/fixtures/` so tests don't depend on a sibling repo. On the UI: **Data Connect → Load Vision fixtures** previews the quoting-agent card (~$0.003 floor, `estimated`) and the move-quote rows ($656, $1,791, …) side by side. Merge into workspace keeps the agent GDR for Inbox; move invoices are **not** written as `outcomes`.

---

## Why YAML matters

This is the part I'm most stubborn about. Verdicts and recommended actions are **not hardcoded in Python**. The profile's vertical loads a `semantics.yaml` file, and that file governs policy. Same exception signal, different product context, different action:

| Exception | Vertical (profile) | Verdict | Recommended action |
| --- | --- | --- | --- |
| `capability_harm` | `agent_runtime` (`assistant_heavy`) | destructive | **rollback** |
| `capability_harm` | `capability_lifecycle` (`workspace_crm`) | destructive | **throttle** |

I wanted the rules to live in config, not buried in Python, so anyone could change what "destructive" means without touching code. Edit sample values in YAML, regenerate workspace, Radar cards update. No deploy needed.

What you tune in `semantics.yaml`:

- `classification.thresholds`: when does `classify()` fire? (e.g. `harm_score_min: 0.08`)
- `decision.verdict_rules`: first match wins (categories → verdict)
- `decision.action_map`: verdict → `recommended_action` + `requires_review`
- `decision.commercial_action_map`: price signal → `commercial_action` (clinical YAML routes to `reallocate`, not `raise_list`)

The ontology has a few verticals: `capability_lifecycle`, `agent_runtime`, `marketplace_commerce`, `clinical_runtime`, `orchestration`, `eval_governance`. Details in [`ontology/README.md`](ontology/README.md).

---

## What's here and what's not

**The main thing** is the agentic rebuild: taxonomy, YAML semantics, JSON Schema for the GDR, price block, ranked Radar, Outcome Flywheel. Around that I added the pieces you actually need if someone shows up with traces: Data Connect adapters (OTel / Langfuse / CSV / Vision; prompt bodies get dropped), Version Gate, Decision Inbox, Subgraph Health, Clinical Radar (`openmed_v22`), Executive Summary, a tiny FastAPI in `service/`, and SQLite behind the old JSONL store. None of that replaces LangSmith or Stripe. It sits on top of the join.

**The legacy simulator pages** are still here, under the Legacy nav. Retention, unit economics, marketplace liquidity, CRO, all of it. I didn't delete anything. Those pages use the old customer/transaction model and they still work. They're reference.

**MMM and multi-touch attribution.** I spent a lot of time on these. The Bayesian MMM pipeline with PyMC, adstock curves, diminishing returns, the whole thing. But honestly, it's not the main event here. I left it in for anyone who wants to explore it (`pip install -r requirements-mmm.txt`, then the Attribution page), but I'm not going to pretend it's polished or that it's the point of this repo.

**Default data is still synthetic.** Generators in `data/agentic_generator.py`. The math is real, the numbers are authored. Data Connect will take a file and overlay it; I have not run a full live partner warehouse through every screen yet. [`docs/honesty.md`](docs/honesty.md) is the source of truth for simulated vs associational vs causal.

### What CapEcon does not price (yet)

CapEcon is deliberate about the **supply side**: what it costs to produce a verified outcome, and whether a capability hurts retention. It does **not** estimate survey WTP, conjoint, or Van Westendorp from billing. Optional **demand_fit** (pypricing `LogLogDemandModel`, explicit Fit button in Packaging Lab / Run Economics) estimates own-price elasticity and surplus-optimal list when the SKU-week panel passes the power gate — `claim_type` stays `simulated` or `associational`, not causal. The Packaging Lab prior slider remains the fallback when pypricing is not installed or the panel is underpowered.

**Harm scores are associational**, not causal, unless there's an `experiment_id` on the record. I want to be careful about that distinction. Every GDR carries `evidence.claim_type` so the UI can't "forget."

---

## Getting started

### Installation via pip (v2.0.0)

```bash
pip install capecon
```

For development or to use the Streamlit dashboard:

```bash
git clone https://github.com/b-lavania/CapEcon.git
cd CapEcon
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -e .                           # install in editable mode
pip install -r requirements-dev.txt        # pytest + hypothesis
streamlit run app.py                       # http://localhost:8501
pytest tests/ -m "not slow" --hypothesis-profile=dev
```

Optional dependencies:

```bash
pip install capecon[dev]       # development tools
pip install capecon[mmm]        # Bayesian MMM (PyMC, ArviZ)
pip install capecon[pypricing]  # demand elasticity modeling
pip install capecon[standards]  # standards export (OpenDone, ADP, Policy Cards)
```

### Optional: Node.js for Standards Export

CapEcon supports exporting to OpenDone and ADP formats. These features require Node.js and npm packages:

```bash
# Install Node.js from https://nodejs.org/
npm install -g opendone
npm install -g @adp/core
```

If Node.js or these packages are not installed, the standards export features will fail fast with clear error messages directing you to this section. Core CapEcon functionality does not require Node.js.

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for collaborator setup, fast vs full tests, and the 5-minute walkthrough.

Optional API (CI check / hooks):

```bash
uvicorn service.app:app --port 8088
```

**Synthetic path**

1. **Product Profile** (Setup): pick a preset, hit **Generate workspace** → lands on **Run Economics** (Price)
2. **Version Gate** / **Radar** (The call): ship / hold / rollback; ranked records
3. Orientation strips on every page repeat the cluster question; full atlas under **Reference → Architecture**
4. **Outcome Flywheel** (Learn): write synthetic outcomes back to close the loop

**Real-file path**

1. **Data Connect**: golden OTel fixture (scrub check) or **Load Vision fixtures** (two-record demo)
2. **Merge into workspace**
3. **Decision Inbox**: quoting-agent GDR with `estimated` floor and `reallocate` evidence when a cheaper model holds the band

If you want to play with policy: change the `agent_runtime` destructive action from `rollback` to `shadow` in [`ontology/agent_runtime/semantics.yaml`](ontology/agent_runtime/semantics.yaml), regenerate with `assistant_heavy`, and watch the Radar cards update.

CI: [.github/workflows/ci.yml](.github/workflows/ci.yml)

Further reading: [Information architecture](docs/information_architecture.md) | [Architecture (join)](docs/architecture.md) | [Why this shape](docs/positioning.md) | [Methodology](docs/methodology.md) | [Honesty](docs/honesty.md) | [What to ingest](docs/contracts.md) | [Adapters](docs/adapters.md) | [Outcomes](docs/outcome_contract.md) | [API / hooks](docs/integrations.md) | [Slice 2 audit](docs/slice2_build_audit.md) | [Ontology](ontology/README.md) | [Migration Guide (v1→v2.0)](docs/MIGRATION_GUIDE.md) | [Examples](docs/examples/)

---

## Repository layout

```
CapEcon/
├── app.py                          # grouped nav (Setup / The call / Price / Learn / Config)
├── core/workspace.py               # unified warehouse (agentic + legacy + overlays)
├── core/control_plane.py           # same functions Streamlit and the API call
├── service/app.py                  # optional FastAPI (version-gate, decisions)
├── ontology/
│   ├── exception_taxonomy.py       # named exceptions, owners, playbook hints
│   ├── decision_rules.py           # YAML → verdict/action
│   ├── store.py                    # SQLite + JSONL audit trail
│   ├── shared/*.schema.json        # GrowthDecisionRecord + economics contract (v2.0)
│   └── */semantics.yaml            # per-vertical policy (with optional export sections)
├── analytics/
│   ├── agentic_profile.py          # profile presets + pricing_mode priors
│   ├── decisions.py                # classify, rank, price, emit
│   ├── price_block.py              # floor / cap / dialect sentence
│   ├── commercial.py               # price signal → commercial_action
│   ├── version_gate.py             # ship / hold / rollback (+ commercial hook)
│   ├── clinical_runtime.py         # OpenMed floor/risk split
│   ├── orchestration.py            # handoffs, subgraph GDRs
│   ├── inference/                  # CS, empirical Bayes, SPRT, binomial
│   └── attribution.py              # Bayesian MMM (legacy, PyMC)
├── data/
│   ├── agentic_generator.py        # synthetic agentic warehouse
│   ├── clinical_generator.py       # openmed_v22 clinical_runs
│   ├── case_studies/               # authored capability catalogs
│   └── adapters/                   # OTel, Langfuse, CSV, Vision, market/workflow/rl/macro/abm/finance
├── standards/                      # NEW in v2.0 - standard exporters
│   ├── opendone.py                 # OpenDone exporter (subprocess bridge)
│   ├── opentrajectory.py           # OpenTrajectory exporter (pure Python)
│   ├── adp.py                      # ADP validator (subprocess bridge)
│   ├── policy_cards.py              # Policy Card exporter (pure Python)
│   └── schemas/policy_card.schema.json
├── integrations/                    # NEW in v2.0 - framework adapters
│   ├── langgraph.py                # LangGraph adapter
│   ├── crewai.py                   # CrewAI adapter
│   ├── autogen.py                  # AutoGen adapter
│   └── otel.py                     # Generic OTel bridge
├── metrics/lexicon.yaml            # governed KPI definitions
├── ui/                             # magazine chrome, decision cards, explainers
│   ├── standards_export.py         # NEW in v2.0 - standards export UI
│   ├── adp_compliance.py           # NEW in v2.0 - ADP compliance UI
│   └── policy_card_editor.py       # NEW in v2.0 - Policy Card editor UI
├── pages/                          # Streamlit pages (agentic + legacy)
│   ├── 50_Standards_Export.py      # NEW in v2.0 - standards export page
│   ├── 51_ADP_Compliance.py        # NEW in v2.0 - ADP compliance page
│   └── 52_Policy_Card_Editor.py    # NEW in v2.0 - Policy Card editor page
├── docs/
├── assets/style.css
└── tests/
    ├── test_standards/              # NEW in v2.0 - mocked unit tests
    └── test_integrations/           # NEW in v2.0 - framework adapter tests
```

---

## Standards Integration (v2.0)

CapEcon v2.0 adds support for exporting to external standards for interoperability. **Standards are export formats only - CapEcon's proprietary features remain the primary source of truth.**

### Supported Standards

1. **OpenDone** - Machine-verifiable AI agent task completion contracts
   - Export format for external verification tools
   - Requires Node.js and `npm install -g opendone`
   - Use: Config → Standards Export → OpenDone

2. **OpenTrajectory** - Vendor-neutral format for AI agent trajectories
   - Pure Python implementation (no Node.js required)
   - Export format for external tools
   - Use: Config → Standards Export → OpenTrajectory

3. **ADP (Agent Decision Protocol)** - Open governance framework for autonomous AI agents
   - Optional validation layer for regulatory compliance
   - Requires Node.js and `npm install -g @adp/core`
   - Use: Config → ADP Compliance

4. **Policy Cards** - Machine-readable operational constraints for deployed agents
   - Export format for external policy management tools
   - Pure Python implementation (no Node.js required)
   - Use: Config → Policy Card Editor

### Critical Principle

**Standards are for interoperability, not replacement.** CapEcon's proprietary features remain the differentiator:
- Outcome Definition Kit (templates, verified_by policy, task tiering)
- Price block & pricing dialects (floor/cap, cost_basis hierarchy)
- Commercial actions (dual-axis decisions, PRICE_SIGNALS)
- Decision Inbox & triage (TRIAGE_STATES, ROLE_OWNERS)
- Knapsack optimization (0-1 knapsack, HITL capacity planning)
- Outcome flywheel (closed-loop learning)
- HITL queueing (Erlang-C formula)
- Exception taxonomy (15+ categories)
- Value ledger (demand-side economics)
- Data Connect adapters (OTel, Langfuse, Vision)

These features are **100% preserved** and not replaced by standards.

### JS-to-Python Bridge

OpenDone and ADP use subprocess calls to Node.js binaries. If Node.js or npm packages are not available, features fail fast with clear error messages directing you to install them. Core CapEcon functionality does not require Node.js.

---

## Framework Integrations (v2.0)

CapEcon v2.0 adds adapters for popular agent frameworks. These are **NEW adapters** that do NOT replace existing OTel/Langfuse adapters.

### Supported Frameworks

1. **LangGraph** - LangGraph adapter intercepts node execution
   - Capture tool calls and outcomes
   - Generate GDRs from LangGraph traces
   - Use: `from integrations.langgraph import LangGraphAdapter`

2. **CrewAI** - CrewAI adapter hooks into task execution
   - Capture crew and agent metadata
   - Map crew hierarchy to GDR subjects
   - Use: `from integrations.crewai import CrewAIAdapter`

3. **AutoGen** - AutoGen adapter intercepts agent conversations
   - Extract tool calls and outcomes
   - Map conversation graphs to GDR
   - Use: `from integrations.autogen import AutoGenAdapter`

4. **Generic OTel** - Generic OTel bridge for any OTel-instrumented agent
   - Ingest OTel GenAI spans
   - Convert to OpenTrajectory format
   - Use: `from integrations.otel import OTelAdapter`

### Example Usage

```python
from integrations.langgraph import LangGraphAdapter

adapter = LangGraphAdapter()
gdrs = adapter.ingest_langgraph_trace(langgraph_trace)
```

---

## Migration Guide (v1 → v2.0)

### What Changed in v2.0

1. **Pip packaging** - Installable via `pip install capecon`
2. **Standard fields** - GDR schema v2.0 adds optional `adp`, `opendone_receipt`, `opentrajectory_id` fields
3. **YAML semantics** - Optional `policy_card_export`, `regulatory_mapping`, `evidence_requirements` sections added
4. **New pages** - 3 new standard compliance pages in Config section
5. **New adapters** - Framework adapters for LangGraph, CrewAI, AutoGen, generic OTel

### What's Preserved

- **100% backward compatible** - All existing GDRs remain valid
- **No breaking changes** - Standard fields are optional
- **All proprietary features preserved** - Outcome Definition Kit, price block, commercial actions, triage, flywheel, HITL queueing, exception taxonomy, value ledger, data adapters
- **All existing pages preserved** - 44 existing pages unchanged
- **All existing UI components preserved** - 14 existing components unchanged

### Migration Steps

No migration required for existing users. Standard fields are optional and default to not present. Simply upgrade to v2.0:

```bash
pip install --upgrade capecon
```

---

## Proprietary Features Guide

CapEcon's unique value comes from its proprietary features that are not available in any standard:

### 1. Outcome Definition Kit
- **Templates**: quote_ops, support, analyst, orchestrator
- **verified_by policy**: deterministic_stage, human_confirmation, llm_judge, webhook
- **Task tiering**: S/M/L with footprint, max_loops, list_usd
- **Outcome value mapping**: Prior value USD per outcome_type
- **Readiness gate**: Validates verified_share, known_types_share, missing_columns

### 2. Price Block & Pricing Dialects
- **Three pricing modes**: internal_budget, product_sku, marketplace_take
- **cost_basis hierarchy**: simulated < estimated < allocated < metered
- **floor vs cap distinction**: floor_usd (unit cost) vs cap_usd (budget cap)
- **primary_metric_usd**: cost_of_leaving_live (teaching formula)
- **Ops vs commercial**: Separate axes for runtime and packaging decisions

### 3. Commercial Actions
- **Dual-axis decisions**: Ops (ship, hold, throttle, rollback) vs Commercial (raise_list, split_tier, reallocate)
- **PRICE_SIGNALS**: unpriceable, within_policy, mesh_leak, below_floor, over_cap
- **COMMERCIAL_OWNERS**: mapping to packaging, finance, platform
- **YAML-driven commercial_action_map**: semantics decides what signal means

### 4. Decision Inbox & Triage
- **TRIAGE_STATES**: pending, in_review, resolved, overridden, deferred
- **ROLE_OWNERS**: growth_lead, product, data_science, engineering, founder, finance, customer_success, packaging, deal_desk, platform
- **Owner routing**: By exception category
- **Commercial owner**: Second owner for commercial_action decisions

### 5. Knapsack Optimization
- **0-1 knapsack algorithm**: Maximize expected savings under HITL capacity
- **Dynamic programming selection**: DP table with keep matrix
- **HITL review slots**: Derived from Erlang-C staffing

### 6. Outcome Flywheel
- **Write-back**: retention_delta_14d, churn_happened, actual_run_cost_usd
- **Followed vs overridden comparison**: retention_delta, delegation_rate, churn_rate
- **Causal impact measurement**: effect_pp, ci95, claim_type

### 7. HITL Queueing
- **Erlang-C formula**: M/M/c queue model for P(wait), expected wait
- **Queue parameters**: arrival_rate, service_rate, servers (reviewers)
- **SLA violation check**: p_wait_exceeds_sla based on expected_wait_hr

### 8. Exception Taxonomy
- **15+ exception categories**: activation_leak, habit_collapse, capability_harm, capability_dead, approval_fatigue, trust_break, connector_fragility, run_cost_blowout, loop_exhaustion, quality_drift, eval_regression, outcome_confirmation_gap, eval_drift, cac_ltv_contradiction, instrumentation_debt
- **Owner_role per category**: growth_lead, product, data_science, engineering, founder, finance
- **Playbook hints**: Actionable guidance per exception type

### 9. Value Ledger
- **Outcome value rollup**: Sum of outcome_value_usd per capability/account
- **Time saved value**: (baseline_min * n_runs - agent_min) * hourly / 60
- **Revenue attribution**: Attributed revenue from subscriptions

### 10. Data Connect Adapters
- **OTel adapter**: JSONL ingest, GenAI semantic conventions, prompt scrubbing
- **Langfuse adapter**: JSON export, HTTP pull, trace/observation mapping
- **Vision adapter**: Two-record system (agent GDR + move quotes)
- **Scrubbing**: `data/adapters/scrub.py` removes prompt bodies

---

## Tooling

| What | Packages |
| --- | --- |
| App shell | Streamlit, Plotly |
| Core analytics | pandas, NumPy, SciPy, scikit-learn, lifelines |
| Ontology | jsonschema, PyYAML |
| Optional API | FastAPI, uvicorn, httpx |
| Attribution (legacy) | pymc, arviz |
| Quality | pytest, Hypothesis |

---

## License

Copyright (c) 2026 CapEcon. All rights reserved. Not licensed for redistribution.
