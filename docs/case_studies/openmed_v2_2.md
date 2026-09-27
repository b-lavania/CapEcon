# OpenMed v2.2 case study

CapEcon preset: **`openmed_v22`** · vertical: **`clinical_runtime`** · catalog: [`data/case_studies/openmed_v2_2.yaml`](../../data/case_studies/openmed_v2_2.yaml)

[OpenMed v2.2.0](https://github.com/maziyarpanahi/openmed/releases/tag/v2.2.0) is a local-first clinical SDK (de-identification, grounding, FHIR/OMOP, Maple/Compass). This case study does **not** install or call OpenMed. It authors a **synthetic warehouse** from the public API inventory so Clinical Radar can price **inference + review labor + expected harm** per capability.

## Why review labor is COGS here

In CRM copilots, human review is optional. In clinical assistive software, qualified review is mandatory on every output. When a capability's abstention rate collapses, more spans surface as "confident," the review queue floods, and **cost per verified outcome** rises even if raw inference looks fine. That is the agentic economics story — not HIPAA checkbox compliance.

A specialty medication access operator (benefit verification, prior auth, clinical evidence from notes) is the motivating scenario: unstructured notes → grounded codes → FHIR evidence → human sign-off. Payer rails are **out of scope** for this warehouse.

## Capability map

| Capability | OpenMed surface | Warehouse signal |
| --- | --- | --- |
| `pii_deidentify` | `POST /pii/deidentify/stream` | `phi_in_logs` |
| `clinical_ner` | `POST /analyze` | `span_integrity`, inference $ |
| `concept_grounding` | `ground()` | `abstention_rate`, `grounding_conflict` |
| `fhir_export` | `to_fhir` | `fhir_integrity_ok` |
| `omop_map` | `to_omop` | `vocab_snapshot_ok` |
| `document_intake` | MIME quarantine | `mime_quarantined` |
| `maple_clinical` | MapleClinicalAssistant | `run_cost_blowout` |
| `compass_vlm` | Compass VLM | inference $ |
| `mcp_tools` | MCP boundaries | `prompt_injection_flag` |
| `privacy_gateway` | privacy gateway | review flags |

## Planted negatives (teaching)

| Capability | Exception |
| --- | --- |
| `pii_deidentify` | `phi_leakage` |
| `concept_grounding` | `abstention_collapse` |
| `maple_clinical` | `run_cost_blowout` |
| `fhir_export` | `fhir_integrity_fail` |
| `omop_map` | `vocab_snapshot_drift` |

## Walkthrough

```bash
cd CapEcon
streamlit run app.py
# Product Profile → OpenMed v2.2 → Generate workspace → Clinical Radar
```

Main Radar still emits generic capability GDRs (`cost_of_leaving_live_usd`). Clinical Radar emits separate records (`residual_clinical_risk_usd`, ids `gdr_cln_*`).
