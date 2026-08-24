# Slice 2 build audit

Started 2026-08-22. Scope for this pass: plan phases 0–A only (YAML label + price block + OpenMed floor/risk split). Everything else is listed here so it is not silently forgotten.

## Built in this pass

- `analytics/price_block.py` — label from YAML (dotted or nested), `pricing_mode`, floor formula, weakest-link `cost_basis`, `price_sentence` for three dialects, `cost_basis=` override, sub-cent `format_usd`
- `price_exceptions`, `_price_marketplace_exceptions`, `_price_clinical_exceptions`, and subgraph emit all call `fill_price_block`
- `_METRIC_LABELS` retired; card humanizes the YAML key
- Economics schema gained optional price-block fields
- Presets carry `pricing_mode` and teaching priors (`policy_cpso_cap`, `budget_cap_per_outcome_usd`, `human_baseline_usd`, `reviewer_loaded_hourly_usd`, `review_minutes_per_approval`)
- Clinical: `floor_usd` = (inference + review labor) / n clinical runs; `risk_usd` = expected harm / n; headline `primary_metric_usd` remains the window total so Radar sort does not change
- `internal_budget` omits `list_usd` (does not emit zero)
- Floor omitted when `n_verified == 0` (no fake `$0.00`)
- Tests: `tests/unit/test_price_block.py` plus emit overlay in `test_decision_rules.py`

### A2 — Vision Agent two-record adapter

- `data/adapters/vision.py` — bakeoff `run.json` → agent GDR; historic jobs JSONL → move quote records
- Agent floor is baseline `cost_usd` (`estimated`, token oracle). Bakeoff total `$0.063` is not the floor
- Historic `actuals.price_dollars` → quote `charged_usd`; `trusted` → `invoiced`, `guess|incomplete|excluded` → `reconstructed`
- Headline quotes = `trusted` and `include_in_headline_metrics` (Job 5 stays out)
- `reallocate` lives on `outputs.routing_hint` + `evidence.reallocate` + `decision.commercial_action`. Ops `recommended_action` stays YAML (`throttle` for `run_cost_blowout`)
- `refuse_mixed_units` raises if a move invoice lands on agent `list_usd` / floor
- Workspace tables: `runs` + `usage_events` only. Move invoices are **not** `outcomes`
- Slim fixtures: `tests/fixtures/vision_bakeoff_run.json`, `tests/fixtures/vision_historic_jobs.jsonl` (no sibling-repo dependency at runtime)
- Data Connect: Load Vision fixtures + bakeoff/JSONL upload; Decision Card preview (unit floor when ranking < $1); merge keeps the quoting-agent GDR
- Tests: `tests/unit/test_adapters_vision.py`

## Deliberate ranking vs headline choice

Kept `primary_metric_usd` as the Radar sort key (window total / exception rollup). Floor is a sibling field. Did not change the three `records.sort(...)` lines.

## Not built (plan items left on the table)

### Phase B — Version Gate overlay
- `analytics/version_gate.py` still hardcodes `primary_metric_label: cost_per_successful_outcome`
- `POST /version-gate` does not return `commercial_action` / floor / cap / list
- `projected_cpso` / `policy_cpso_cap` still optional CI decorations, not wired from the new priors automatically on the page
- Bandits under a margin constraint: mentioned in the plan, no phase work

### Commercial verbs
- `ACTIONS` enum unchanged (`ship|hold|throttle|…`). `resolve_action` still rewrites unknown actions to `hold`
- No `hold_sku` / `raise_list` / `split_tier` / `cut_credits` / `kill_all_inclusive` / `reallocate`
- `ACTION_GLOSS` not extended
- YAML `uneconomic` still maps to `hold` or `throttle`

### Theta spine (explicitly after A)
- No `source_event_id`, per-exception `human_loop`, `inputs` / `context` / `outputs`, `ids.json`
- No record lifecycle Draft → Review → Exported → Closed

### Value metric / flywheel / meter
- Outcome Definition kit does not refuse `list_usd` without a verified outcome (product_sku still implies list from MRR/tokens when n_verified > 0)
- Flywheel still writes retention delta, not `margin_variance_usd`
- No meter export (`outcome_id → charged_usd → claim_type`)
- No `outputs.price_book_action` hook

### Allocation / Qortex / docs / packaging
- Orchestration dollars are on the price block only via generic run-cost floor, not per-edge tax
- No Qortex `outcomes.json` adapter; no Gemini `usage_metadata` field
- No Projection (`command|coordinator|composer`) field suppression
- Docs (`positioning.md`, `contracts.md`, `honesty.md`, README) not rewritten for the unit-of-account sentence
- Product Profile has no `pricing_mode` override widget (preset field only)
- Data Connect has no oracle-override upload
- `pages/26_Agent_Version_Compare.py` still duplicates Version Gate
- Foundry-style `associational` → `causal` promotion ritual: not started

### Honesty / data gaps this pass did not close

- Synthetic workspaces are `cost_basis: simulated`. Uploaded traces without invoices become `estimated`, never `metered`
- `list_usd` for `product_sku` is always `implied` / `reconstructed` — no price-book CSV
- HITL dollars use `len(approvals) × review_minutes_per_approval × hourly` because approvals have no `review_minutes` column
- Coordination / connector tax on the floor formula is **not** allocated (terms exist in the plan; emit uses inference + HITL only)
- Clinical denominator is **clinical_runs rows**, not `outcomes.verified`
- Unattributed spend still falls back to a teaching 18% when usage events lack `attribution_complete`
- Fourth hardcoded label in version_gate left in place (see Phase B)
- Vision bakeoff remains `estimated` (token oracle + `cost_pricing_as_of`), not a Google invoice
- Historic JSONL has no `price_min/max`; `price_in_band` only if a scored-eval map is attached
- Quote records are session-side (`quote_records`); Inbox still shows the agent GDR only
- Theta `MoveQuoteRecord` schema is not vendored; quote records are theta-shaped JSON, not validated as GDRs

## Missed relative to the letter of phase A (called out)

1. **Product Profile UI** for `pricing_mode` / budget cap / baseline — plan listed it as an input; only preset JSON was updated
2. **`economics.primary_metric_display` in YAML** — helper supports it; no YAML file actually sets it (card humanizes the key instead)
3. **Golden OTel → floor vs list** — not extended; tests hang on emit + unit helpers as the plan's executability pass required
4. **Marketplace dialect on the card** is a caption via `price_sentence`; no dedicated take-rate chip
5. **SQLite / stored GDRs** — old payloads without the block still load; no backfill
6. **`pages/17_Run_Economics.py` and `pages/2_Unit_Economics.py`** — not reframed around the price sentence
7. **Inbox `owner_role` for packaging/finance** — not added
8. **OpenMed YAML `pricing_mode`** lives on the preset, not in `semantics.yaml`

## What would still go wrong if someone "finished the plan" from here

- Wiring Vision historic invoices onto `list_usd`
- Treating bakeoff API `$` as `metered`
- Bundling theta spine into the next price-block tweak
- Adding commercial YAML actions without growing `ACTIONS` (ops vs commercial already split; `reallocate` is evidence + commercial_action, not `recommended_action`)
