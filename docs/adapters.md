# CapEcon adapters (econ-world exports)

CapEcon is the **decision join**: Workspace tables → GrowthDecisionRecord → Radar / Run Economics.
It does **not** run Magentic Marketplace, HARK, Econojax, TwinMarket, or similar simulators.
Those projects simulate. CapEcon prices and decides after you export a file and overlay it on **Data Connect**.

## Categories

| Adapter | Example upstream shape | Workspace tables | Default `claim_type` |
| --- | --- | --- | --- |
| `market` | Magentic Marketplace / MarketAgents | `agent_transactions`, `runs`, `outcomes` | `simulated` |
| `workflow` | OTel / Langfuse / LangGraph nodes | `runs`, `spans`, optional `approvals` | `associational` for OTel/Langfuse; `simulated` for LangGraph dumps |
| `rl` | Econojax / AI Economist episode logs | `runs` (+ `reward`, `n_steps`) | `simulated` |
| `macro` | EconAgent / LLM-Economist periods | `outcomes`, `usage_events` | `simulated` |
| `abm` | HARK / scikit-agent scenario summary | `accounts`, `outcomes`, `usage_events` | `simulated` |
| `finance` | TwinMarket-style blotter | `runs`, `outcomes` (+ `pnl_usd`, optional `latency_ms`) | `simulated` |
| `token_econ` | RouteLLM / FrugalGPT cascade logs | `runs`, `usage_events`, `routing_log` | `associational` |

Existing adapters (`otel`, `langfuse`, `csv`, `vision`) stay as they are. `workflow` may call OTel/Langfuse parsers.

## Contract

1. Accept a **local file** (JSON / JSONL). Never call the upstream project at runtime.
2. Emit `{"tables": dict[str, DataFrame], "meta": {...}}` aligned to columns in `core/workspace.py` / `docs/contracts.md`.
3. Stamp `ingest_source`, `adapter_id`, `evaluator_id` (`capecon_<category>_adapter`), `claim_type`.
4. Scrub prompts via `data.adapters.scrub.scrub_payload`.
5. Ship a golden fixture under `tests/fixtures/adapters/<category>/sample.jsonl`.

## Provenance

Simulated market / macro / RL / ABM / finance numbers are **not** ChartMogul NRR or production billing.
`claim_type` stays `simulated` unless the export is a real OTel/Langfuse trace with join keys (`associational`).
`token_econ` overlays are stamped `associational` (routing telemetry, not invoices).
Presets `agentic_commerce` and `frugal_router` price those exports; they do not run Magentic Marketplace or RouteLLM.
`causal` still requires an experiment id on the subject.

## Fixtures

Hand-authored minimal shapes. Not vendored from upstream repos.
