"""Named third-party SDK case catalogs for clinical_runtime presets."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CASE_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=16)
def load_case_study(case_study_id: str) -> dict[str, Any]:
    path = _CASE_DIR / f"{case_study_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Unknown case study: {case_study_id} ({path})")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid case study YAML: {case_study_id}")
    return data


def capability_ids_from_catalog(catalog: dict[str, Any]) -> list[str]:
    caps = catalog.get("capabilities") or []
    return [str(c["id"]) for c in caps if c.get("id")]


def apply_case_study_to_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Merge catalog-derived priors into a preset copy."""
    case_id = profile.get("case_study_id")
    if not case_id:
        return profile
    catalog = load_case_study(case_id)
    priors = dict(profile.get("priors") or {})
    ids = capability_ids_from_catalog(catalog)
    priors["n_capabilities"] = len(ids)
    priors["capability_ids"] = ids
    profile = dict(profile)
    profile["priors"] = priors
    profile["case_study"] = {
        "case_study_id": catalog.get("case_study_id", case_id),
        "sdk": catalog.get("sdk"),
        "release": catalog.get("release"),
        "source_url": catalog.get("source_url"),
        "honesty": catalog.get("honesty"),
    }
    return profile
