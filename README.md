# churnOS

Figuring out how agentic products should handle churn, retention, and monetization, and what it actually costs to leave a capability live.

---

## How this started

The first version of this was a bunch of spreadsheets. Retention curves, churn cohort breakdowns, attribution models for a couple of marketplaces and ecomm stores I was studying. I was trying to answer the same question everyone asks: *why are people leaving, and what can we actually do about it?*

Those spreadsheets turned into a Python project. I built out a causal waterfall, survival models, experimentation scaffolding, even a full Bayesian MMM pipeline with PyMC. It worked, in the sense that the math was sound, but it was still fundamentally about customers and transactions. Traditional SaaS/ecomm retention.

Then I started paying attention to agentic products (AI assistants, CRM copilots, ops agents) and realized the retention problem is completely different there: you're not retaining customers in the old sense, instead you're shipping features (skills, automations, agent tools).

So the question becomes: is this capability helping or hurting? Is it worth the inference cost? Should we throttle it, roll it back, or kill it entirely? The old spreadsheet models didn't have a place for that; I rebuilt the whole thing around capabilities instead of customers and that's ***churnOS***.

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

---

## Data Connect, including Vision (two records)

**Data Connect** is where real files land: OTel JSONL, Langfuse export, CSVs for accounts/outcomes/subscriptions/usage, and now a **Vision Agent** pack.

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

### What churnOS does not price (yet)

churnOS is deliberate about the **supply side**: what it costs to produce a verified outcome, and whether a capability hurts retention. It does **not** estimate survey WTP, conjoint, or Van Westendorp from billing. Optional **demand_fit** (pypricing `LogLogDemandModel`, explicit Fit button in Packaging Lab / Run Economics) estimates own-price elasticity and surplus-optimal list when the SKU-week panel passes the power gate — `claim_type` stays `simulated` or `associational`, not causal. The Packaging Lab prior slider remains the fallback when pypricing is not installed or the panel is underpowered.

**Harm scores are associational**, not causal, unless there's an `experiment_id` on the record. I want to be careful about that distinction. Every GDR carries `evidence.claim_type` so the UI can't "forget."

---

## Getting started

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for collaborator setup, fast vs full tests, and the 5-minute walkthrough.

```bash
cd churnOS
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt          # core app (+ FastAPI)
pip install -r requirements-dev.txt      # pytest + hypothesis
streamlit run app.py                     # http://localhost:8501
pytest tests/ -m "not slow" --hypothesis-profile=dev
```

Optional API (CI check / hooks):

```bash
uvicorn service.app:app --port 8088
```

**Synthetic path**

1. **Product Profile**: pick a preset, hit **Generate workspace**
2. **Version Gate**: ship / hold / rollback on the latest two capability versions
3. **Radar** or **Decision Inbox**: ranked records, read the price sentence, override if you disagree
4. **Outcome Flywheel**: write synthetic outcomes back to close the loop

**Real-file path**

1. **Data Connect**: golden OTel fixture (scrub check) or **Load Vision fixtures** (two-record demo)
2. **Merge into workspace**
3. **Decision Inbox**: quoting-agent GDR with `estimated` floor and `reallocate` evidence when a cheaper model holds the band

If you want to play with policy: change the `agent_runtime` destructive action from `rollback` to `shadow` in [`ontology/agent_runtime/semantics.yaml`](ontology/agent_runtime/semantics.yaml), regenerate with `assistant_heavy`, and watch the Radar cards update.

CI: [.github/workflows/ci.yml](.github/workflows/ci.yml)

Further reading: [Why this shape](docs/positioning.md) | [Methodology](docs/methodology.md) | [Honesty](docs/honesty.md) | [What to ingest](docs/contracts.md) | [Outcomes](docs/outcome_contract.md) | [API / hooks](docs/integrations.md) | [Slice 2 audit](docs/slice2_build_audit.md) | [Ontology](ontology/README.md)

---

## Repository layout

```
churnOS/
├── app.py                          # grouped nav (START / DECIDE / LEARN / CONFIG)
├── core/workspace.py               # unified warehouse (agentic + legacy + overlays)
├── core/control_plane.py           # same functions Streamlit and the API call
├── service/app.py                  # optional FastAPI (version-gate, decisions)
├── ontology/
│   ├── exception_taxonomy.py       # named exceptions, owners, playbook hints
│   ├── decision_rules.py           # YAML → verdict/action
│   ├── store.py                    # SQLite + JSONL audit trail
│   ├── shared/*.schema.json        # GrowthDecisionRecord + economics contract
│   └── */semantics.yaml            # per-vertical policy
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
│   └── adapters/                   # OTel, Langfuse, CSV, Vision (scrubs prompts)
├── metrics/lexicon.yaml            # governed KPI definitions
├── ui/                             # magazine chrome, decision cards, explainers
├── pages/                          # Streamlit pages (agentic + legacy)
├── docs/
├── assets/style.css
└── tests/
```

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

Copyright (c) 2026 churnOS. All rights reserved. Not licensed for redistribution.
