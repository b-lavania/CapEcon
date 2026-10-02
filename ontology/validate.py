"""Ontology registry and validation for agentic CapEcon."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ONTOLOGY_ROOT = Path(__file__).resolve().parent

VERTICALS = {
    "capability_lifecycle": {
        "semantics": ONTOLOGY_ROOT / "capability_lifecycle" / "semantics.yaml",
        "schema": ONTOLOGY_ROOT / "shared" / "growth_decision_record.base.schema.json",
    },
    "agent_runtime": {
        "semantics": ONTOLOGY_ROOT / "agent_runtime" / "semantics.yaml",
        "schema": ONTOLOGY_ROOT / "shared" / "growth_decision_record.base.schema.json",
    },
    "orchestration": {
        "semantics": ONTOLOGY_ROOT / "orchestration" / "semantics.yaml",
        "schema": ONTOLOGY_ROOT / "shared" / "growth_decision_record.base.schema.json",
    },
    "eval_governance": {
        "semantics": ONTOLOGY_ROOT / "eval_governance" / "semantics.yaml",
        "schema": ONTOLOGY_ROOT / "shared" / "growth_decision_record.base.schema.json",
    },
    "marketplace_commerce": {
        "semantics": ONTOLOGY_ROOT / "marketplace_commerce" / "semantics.yaml",
        "schema": ONTOLOGY_ROOT / "shared" / "growth_decision_record.base.schema.json",
    },
    "clinical_runtime": {
        "semantics": ONTOLOGY_ROOT / "clinical_runtime" / "semantics.yaml",
        "schema": ONTOLOGY_ROOT / "shared" / "growth_decision_record.base.schema.json",
    },
    "agentic_commerce": {
        "semantics": ONTOLOGY_ROOT / "agentic_commerce" / "semantics.yaml",
        "schema": ONTOLOGY_ROOT / "shared" / "growth_decision_record.base.schema.json",
    },
}


def schema_path(vertical: str) -> Path:
    return VERTICALS[vertical]["schema"]


def load_schema(vertical: str) -> dict[str, Any]:
    with open(schema_path(vertical)) as f:
        return json.load(f)


def validate_record(record: dict[str, Any], vertical: str) -> list[str]:
    try:
        import jsonschema
        from jsonschema import RefResolver
    except ImportError:
        return []

    schema = load_schema(vertical)
    store = {
        schema["$id"]: schema,
        f"https://capecon.local/ontology/shared/exception_item.schema.json": json.loads(
            (ONTOLOGY_ROOT / "shared" / "exception_item.schema.json").read_text()
        ),
        f"https://capecon.local/ontology/shared/economics.schema.json": json.loads(
            (ONTOLOGY_ROOT / "shared" / "economics.schema.json").read_text()
        ),
        f"https://capecon.local/ontology/shared/decision.schema.json": json.loads(
            (ONTOLOGY_ROOT / "shared" / "decision.schema.json").read_text()
        ),
    }
    resolver = RefResolver.from_schema(schema, store=store)
    validator = jsonschema.Draft202012Validator(schema, resolver=resolver)
    return [e.message for e in validator.iter_errors(record)]


if __name__ == "__main__":
    from ontology.__main__ import main
    import sys

    sys.exit(main())
