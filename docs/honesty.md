# Honesty & limits (synthetic demo)

CapEcon is a **synthetic teaching environment** unless you overlay files on Data Connect. Numbers illustrate methodology and decision workflows; they are not production telemetry from a customer.

## What is real vs simulated

| Layer | Status |
| --- | --- |
| Warehouse tables | Authored in `data/agentic_generator.py`. Data Connect can overlay OTel / CSV / Langfuse / Vision / market / workflow / RL / macro / ABM / finance / token_econ exports. I have not run a live partner warehouse through this yet. |
| Metric formulas | Teaching definitions aligned to `docs/methodology.md` |
| GDR exceptions | Heuristic classifiers on whatever is in the warehouse |
| Causal claims | Only when `experiment_id` is present on a record |
| Outcome flywheel | Simulated write-back using generator ground truth, unless you supplied real `outcomes` |

## Associational vs causal

- **Associational:** correlation-style signals (usage ↔ churn uplift, drift WoW). Shown with confidence, not causal verdicts.
- **Causal gate:** `subject.experiment_id` + experiment tables. Without it, records must not claim causal harm.
- **Simulated:** default `claim_type` when `meta.data_source` is the generator / mock OTel, or a market / RL / macro / ABM / finance fixture. Simulated market and macro numbers are not production telemetry. `token_econ` routing overlays are `associational` telemetry (not billing).
- **Human override:** `decision.final_action` may differ from `recommended_action`; flywheel compares followed vs overridden cohorts.

Every emitted GDR should carry `evidence.claim_type`. If the UI doesn't show it, that's a bug.

## Teaching formulas

- **Cost of leaving live** (`economics.primary_metric_usd`): rollup of LTV-at-risk + run cost for capabilities; LTV teaching formula for accounts.
- **CM-NRR:** contribution-margin net revenue retention on synthetic subscriptions (or overlaid ones).
- **$/successful outcome:** gross run cost / verified successful outcomes in window.
- **Value / surplus:** optional `economics.value_usd` and `surplus_usd` from outcome values, revenue joins, or Outcome Definition priors. Associational or prior unless measured with an experiment.
- **WTP cap (rigorous):** data-derived `cap_usd` from subscriptions when n is sufficient; when `workspace.meta.demand_fit` is populated (Packaging Lab or Run Economics **Fit demand**), rigorous mode prefers per-SKU `surplus_opt_usd` from the fitted log-log model. Install optional deps: `pip install -r requirements-pricing.txt`.
- **Demand elasticity:** pypricing MCMC runs only on explicit Fit — never inside `classify()`. Synthetic warehouse → `claim_type: simulated`; Data Connect overlay → `associational`. Causal demand claims require `experiment_id` on a price arm (not built in v1).

## Data storage

- GDR audit trail: SQLite + JSONL via `ontology/store.py` (local).
- No raw prompts. Adapters in `data/adapters/` drop known content keys; `tests/unit/test_adapters_scrub.py` is the check.

For the full retention methodology, see [`methodology.md`](methodology.md).

## OpenMed v2.2 case study (`openmed_v22` preset)

- Warehouse rows are **authored from public OpenMed 2.2 API contracts**, not vendor telemetry.
- OpenMed is **not** claimed to have a churn problem; CapEcon prices **review labor as COGS** on assistive clinical output.
- GDRs and `clinical_runs` store **hashes, rates, counts, and USD** — never source clinical text or MRNs.
- See [`case_studies/openmed_v2_2.md`](case_studies/openmed_v2_2.md).
