# churnOS

Figuring out how agentic products should handle churn, retention, and monetization.

---

## How this started

The first version of this was a bunch of spreadsheets. Retention curves, churn cohort breakdowns, attribution models for a couple of marketplaces and ecomm stores I was studying. I was trying to answer the same question everyone asks: *why are people leaving, and what can we actually do about it?*

Those spreadsheets turned into a Python project. I built out a causal waterfall, survival models, experimentation scaffolding, even a full Bayesian MMM pipeline with PyMC. It worked, in the sense that the math was sound, but it was still fundamentally about customers and transactions. Traditional SaaS/ecomm retention.

Then I started paying attention to agentic products (AI assistants, CRM copilots, ops agents) and realized the retention problem is completely different there: you're not retaining customers in the old sense, instead you're shipping features (skills, automations, agent tools).

So, the question becomes: is this capability helping or hurting? Is it worth the inference cost? Should we throttle it, roll it back, or kill it entirely? The old spreadsheet models didn't have a place for that; I rebuilt the whole thing around capabilities instead of customers and that's ***churnOS***.

The follow-on question, once you have more than one agent in production, is even less pretty: did this *version* make things better or worse, and can you tell before the customer does? That's what **Version Gate** is for. I still don't want this repo to be another agent runtime. There are already too many of those.

---

## What it actually does

You pick a product profile (what kind of agentic product are you?), generate a synthetic warehouse of seats, capabilities, agent runs, approvals, and connectors — or overlay a real OTel/Langfuse export plus CSVs on **Data Connect** — and then the engine classifies exceptions, prices the cost of leaving things as they are, and gives you ranked decisions.

```text
Profile (ontology switch)  /  Data Connect (optional overlay)
   > Warehouse (seats, capabilities, runs, approvals, connectors, outcomes)
   > Classify (exceptions from thresholds)
   > YAML rules (verdict > recommended action)     < edit policy here
   > GrowthDecisionRecord
   > Version Gate / Radar / Decision Inbox
   > Outcome Flywheel (write-back onto the same record)
```

The loop, step by step:

1. **Profile** Pick a preset (`assistant_heavy`, `workspace_crm`, `ops_mission`, `marketplace_agentic`, `openmed_v22`, etc.). That switches the ontology vertical and the synthetic priors. If you have files, **Data Connect** first.
2. **Outcomes** If you can't name what "verified success" means, stop and use **Outcome Definition**. Login is not an outcome.
3. **Generate / overlay** Build the warehouse. Synthetic by default.
4. **Version Gate** Should this capability version ship, hold, or roll back? SPRT + eval delta. Same logic is on `POST /version-gate` if you want a CI check.
5. **Radar / Inbox** Rank by `cost_of_leaving_live_usd`. Override if you disagree. Inbox is the same cards with a triage state.
6. **Close loop** Outcome Flywheel writes `retention_delta` and `churn_happened` back onto the same record.

---

## Why YAML matters

This is the part I'm most stubborn about. Verdicts and recommended actions are **not hardcoded in Python**. The profile's vertical loads a `semantics.yaml` file, and that file governs policy. Same exception signal, different product context, different action:


| Exception         | Vertical (profile)                       | Verdict     | Recommended action |
| ----------------- | ---------------------------------------- | ----------- | ------------------ |
| `capability_harm` | `agent_runtime` (`assistant_heavy`)      | destructive | **rollback**       |
| `capability_harm` | `capability_lifecycle` (`workspace_crm`) | destructive | **throttle**       |


I wanted the rules to live in config, not buried in Python, so anyone could change what "destructive" means without touching code. Edit sample values in YAML, regenerate workspace, Radar cards update. No deploy needed.

What you tune in `semantics.yaml`:

- `classification.thresholds` when does `classify()` fire? (e.g. `harm_score_min: 0.08`)
- `decision.verdict_rules` first match wins (categories to verdict)
- `decision.action_map` verdict to `recommended_action` + `requires_review`

The ontology has a few verticals: `capability_lifecycle`, `agent_runtime`, `marketplace_commerce`, `orchestration`, `eval_governance`. The first three get the most use. `orchestration` is the multi-agent handoff / subgraph one. Details in `[ontology/README.md](ontology/README.md)`.

---

## What's here and what's not

**The main thing** is still the agentic rebuild: taxonomy, YAML semantics, JSON Schema for the `GrowthDecisionRecord`, ranked Radar, Outcome Flywheel. Around that I added the pieces you actually need if someone shows up with traces: Data Connect adapters (OTel / Langfuse / CSV — prompt bodies get dropped), Version Gate, a Decision Inbox, Subgraph Health, a one-pager Executive Summary, a tiny FastAPI in `service/`, and SQLite behind the old JSONL store. None of that replaces LangSmith or Stripe. It sits on top of the join.

**The legacy simulator pages** are still here, under the Legacy nav. Retention, unit economics, marketplace liquidity, CRO, all of it. I didn't delete anything. Those pages use the old customer/transaction model and they still work. They're reference.

**MMM and multi-touch attribution.** I spent a lot of time on these. The Bayesian MMM pipeline with PyMC, adstock curves, diminishing returns, the whole thing. But honestly, it's not the main event here. I left it in for anyone who wants to explore it (`pip install -r requirements-mmm.txt`, then the Attribution page), but I'm not going to pretend it's polished or that it's the point of this repo.

**Default data is still synthetic.** Generators in `data/agentic_generator.py`. The math is real, the numbers are authored. Data Connect will take a file and overlay it; I have not run this against a live partner warehouse yet. `[docs/honesty.md](docs/honesty.md)` is the source of truth for simulated vs associational vs causal.

**Harm scores are associational**, not causal, unless there's an `experiment_id` on the record. I want to be careful about that distinction. Every GDR now carries `evidence.claim_type` so the UI can't "forget."

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

1. Open **Product Profile**, pick a preset, hit **Generate workspace** (or **Data Connect** → golden OTel fixture if you want to see ingest)
2. **Version Gate** — ship / hold / rollback on the latest two capability versions
3. **Radar** or **Decision Inbox** — ranked records, override if you disagree
4. **Outcome Flywheel** — write synthetic outcomes back to close the loop

If you want to play with policy: change the `agent_runtime` destructive action from `rollback` to `shadow` in `[ontology/agent_runtime/semantics.yaml](ontology/agent_runtime/semantics.yaml)`, regenerate with `assistant_heavy`, and watch the Radar cards update.

CI: [.github/workflows/ci.yml](.github/workflows/ci.yml)

Further reading: [Why this shape](docs/positioning.md), [Methodology](docs/methodology.md), [Honesty](docs/honesty.md), [What to ingest](docs/contracts.md), [Outcomes](docs/outcome_contract.md), [API / hooks](docs/integrations.md), [How it's packaged](docs/deployment.md), [Who to talk to](docs/partners.md), [Ontology](ontology/README.md)

---

## Repository layout

```
churnOS/
├── app.py                          # grouped nav (START / DECIDE / LEARN / CONFIG)
├── core/workspace.py               # Unified warehouse (agentic + legacy + overlays)
├── core/control_plane.py           # Same functions Streamlit and the API call
├── service/app.py                  # Optional FastAPI (version-gate, decisions)
├── ontology/
│   ├── exception_taxonomy.py       # Named exceptions, owners, playbook hints
│   ├── decision_rules.py           # YAML to verdict/action
│   ├── store.py                    # SQLite + JSONL audit trail
│   ├── shared/*.schema.json        # GrowthDecisionRecord contract
│   └── */semantics.yaml            # per-vertical policy
├── analytics/
│   ├── agentic_profile.py          # Profile presets
│   ├── decisions.py                # Classify, rank, price, emit
│   ├── version_gate.py             # Ship / hold / rollback
│   ├── orchestration.py            # Handoffs, subgraph GDRs
│   ├── marketplace_economics.py    # Agent-assisted GMV margin
│   ├── inference/                  # CS, empirical Bayes, SPRT, binomial
│   ├── drift.py                    # KL/JS mix drift, CUSUM
│   ├── token_risk.py               # VaR/CVaR, price shock
│   └── attribution.py             # Bayesian MMM (legacy, PyMC)
├── data/
│   ├── agentic_generator.py        # Synthetic agentic warehouse
│   ├── generator.py                # Legacy customers/funnel/events
│   └── adapters/                   # OTel, Langfuse, CSV (scrubs prompts)
├── metrics/lexicon.yaml            # Governed KPI definitions
├── ui/                             # Magazine chrome, decision cards, explainers
├── pages/                          # Streamlit pages (agentic + legacy)
├── docs/
├── assets/style.css
└── tests/
```

---

## Tooling


| What                 | Packages                                      |
| -------------------- | --------------------------------------------- |
| App shell            | Streamlit, Plotly                             |
| Core analytics       | pandas, NumPy, SciPy, scikit-learn, lifelines |
| Ontology             | jsonschema, PyYAML                            |
| Optional API         | FastAPI, uvicorn, httpx                       |
| Attribution (legacy) | pymc, arviz                                   |
| Quality              | pytest, Hypothesis                            |


---

## License

Copyright (c) 2026 churnOS. All rights reserved. Not licensed for redistribution.
