# Math dojo contributor guide

Every rigorous method in churnOS ships as:

1. **Pure function** in `analytics/` (no Streamlit)
2. **Unit + property tests** in `tests/`
3. **Math Lab** page under Learn nav (optional for backlog items)
4. **The call / Learn hook** — operator-facing so-what on Radar, Version Gate, or Flywheel
5. **Optional `evidence` block** on GDR exceptions when `profile.priors.math_mode == "rigorous"`

## Ground truth

`data/ground_truth.py` stores planted latents per seed. Tests assert estimators recover truth within tolerance.

## Honesty

- `claim_type: causal` requires `experiment_id` — see `docs/honesty.md`
- Default `math_mode` is `heuristic`; toggle on Product Profile

## Modules

| Module | Estimand | UI surface |
| --- | --- | --- |
| `analytics/inference/binomial.py` | churn rate posterior | Math Lab Binomial |
| `analytics/survival.py` | P(churn_30d), fitted hazard, calibration, attributions | Radar, Decision Card, Lab · Calibration |
| `analytics/stochastic_economics.py` | CM-NRR bootstrap, conformal CPSO/risk/$ bands | Run Economics, Radar |
| `analytics/decision_curves.py` | net-benefit vs threshold | Lab · Decision Curves |
| `analytics/knapsack.py` | intervention selection under HITL capacity | Radar, Run Economics |
| `analytics/bandits.py` | YAML Thompson traffic + regret | Version Compare |
| `analytics/experimentation.py` | clustered sample size, CUPED, FDR | Math Lab Power |
| `analytics/agent_version_compare.py` | SPRT version decision | Version Gate |
| `analytics/causal_uplift.py` | uplift_pp | capability_harm evidence |
| `analytics/clv_probabilistic.py` | BG/NBD CLV (legacy) | Math Lab CLV |
| `analytics/queueing.py` | Erlang-C HITL wait | Run Economics |
| `analytics/pareto.py` | success×cost×trust frontier | Radar (pareto mode) |
| `analytics/inference/confidence_sequences.py` | always-valid proportion CS | Version Compare |
| `analytics/drift.py` | KL/JS mix drift, CUSUM change-point | Math Lab Drift, classify |
| `analytics/inference/empirical_bayes.py` | Beta–Binomial harm shrinkage | Binomial lab, classify harm |
| `analytics/token_risk.py` | daily spend VaR/CVaR, price shock | Run Economics, Marketplace Radar |
| `analytics/marketplace_economics.py` | platform margin after inference | Marketplace Radar |

## Acceptance per PR

Analytics + tests + at least one The call / Learn surface + estimand gloss in `ui/explain.py`.
