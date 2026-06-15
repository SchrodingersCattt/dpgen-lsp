"""Offline DP-GEN rule/provenance index derived from official documentation."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any


@lru_cache(maxsize=1)
def load_rule_index() -> dict[str, Any]:
    path = files("dpgen_lsp.schema").joinpath("dpgen_rules.json")
    return json.loads(path.read_text(encoding="utf-8"))


def source_provenance() -> list[dict[str, Any]]:
    return list(load_rule_index().get("sourceProvenance", []))


def workflow_index(workflow: str) -> dict[str, Any]:
    return dict(load_rule_index().get("workflows", {}).get(workflow, {}))


def machine_index() -> dict[str, Any]:
    return dict(load_rule_index().get("machine", {}))


def field_metadata(workflow: str, field: str) -> dict[str, Any] | None:
    index = machine_index() if workflow == "machine" else workflow_index(workflow)
    fields = index.get("fields", {})
    if field in fields:
        return dict(fields[field])
    short = field.rsplit(".", 1)[-1]
    if short in fields:
        return dict(fields[short])
    return None


def manual_ref_for(workflow: str, *, field: str = "", code: str = "") -> str | None:
    index = machine_index() if workflow == "machine" else workflow_index(workflow)
    rules = index.get("rules", {})
    if code and code in rules:
        return rules[code].get("manual_ref")
    if field:
        meta = field_metadata(workflow, field)
        if meta:
            return meta.get("manual_ref")
    return index.get("manualRef")


def pipeline_steps() -> list[str]:
    return list(load_rule_index().get("pipeline", []))
