"""Diagnostics provider combining JSON parse, schema, and lint checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..schema.loader import SchemaTree, load_schema_tree, detect_workflow
from ..schema.json_path import is_json


def _range(line: int, character: int, length: int = 1) -> dict:
    return {
        "start": {"line": line, "character": character},
        "end": {"line": line, "character": character + max(length, 1)},
    }


def _diagnostic(
    line: int,
    character: int,
    message: str,
    severity: str = "error",
    code: str = "diagnostic",
    length: int = 1,
    category: str = "schema",
    fix_hints: list[str] | None = None,
    blocking: bool = True,
) -> dict:
    return {
        "code": code,
        "severity": severity,
        "category": category,
        "confidence": 1.0,
        "source": "dpgen-lsp",
        "range": _range(line, character, length),
        "message": message,
        "fix_hints": fix_hints or [],
        "blocking": blocking,
    }


class DiagnosticProvider:

    def __init__(self):
        self._schema_cache: dict[str, SchemaTree] = {}

    def get_diagnostics(self, text: str, uri: str = "") -> list[dict]:
        diagnostics: list[dict] = []

        if not text.strip():
            return diagnostics

        try:
            json.loads(text)
        except json.JSONDecodeError as e:
            diagnostics.append(_diagnostic(
                e.lineno - 1 if e.lineno else 0,
                e.colno - 1 if e.colno else 0,
                f"JSON parse error: {e.msg}",
                severity="error",
                code="json.parse_error",
                category="syntax",
            ))
            return diagnostics

        try:
            data = json.loads(text)
        except Exception:
            return diagnostics

        workflow = detect_workflow(text)
        schema = self._get_schema(workflow)
        if schema.root is None:
            return diagnostics

        try:
            from dargs import Argument
            arginfo_module = __import__(schema.workflow_map[schema.workflow]["module"], fromlist=[schema.workflow_map[schema.workflow]["func"]])
            arginfo_func = getattr(arginfo_module, schema.workflow_map[schema.workflow]["func"])
            arg = arginfo_func()
            arg.check_value(data, strict=False)
        except ImportError:
            pass
        except Exception as e:
            diagnostics.append(_diagnostic(
                0, 0,
                f"Schema validation: {e}",
                severity="error",
                code="schema.validation",
                category="schema",
            ))

        lint_diags = _lint_checks(data, text)
        diagnostics.extend(lint_diags)

        return diagnostics

    def _get_schema(self, workflow: str) -> SchemaTree:
        if workflow not in self._schema_cache:
            try:
                self._schema_cache[workflow] = load_schema_tree(workflow)
            except Exception:
                self._schema_cache[workflow] = SchemaTree(workflow)
        return self._schema_cache[workflow]


def _lint_checks(data: dict, text: str) -> list[dict]:
    diagnostics: list[dict] = []

    type_map_len = len(data.get("type_map", []))
    mass_map_val = data.get("mass_map", [])
    if isinstance(mass_map_val, list) and mass_map_val != "auto" and len(mass_map_val) != type_map_len:
        diagnostics.append(_lint_simple(
            "mass_map",
            "mass_map length should match type_map length",
            "type/value",
            text,
        ))

    fp_task_max = data.get("fp_task_max", 0)
    fp_task_min = data.get("fp_task_min", 0)
    if fp_task_max > 0 and fp_task_min > 0 and fp_task_max < fp_task_min:
        diagnostics.append(_lint_simple(
            "fp_task_max",
            "fp_task_max should be >= fp_task_min",
            "type/value",
            text,
        ))

    f_lo = data.get("model_devi_f_trust_lo", 0)
    f_hi = data.get("model_devi_f_trust_hi", 1)
    if isinstance(f_lo, (int, float)) and isinstance(f_hi, (int, float)) and f_lo >= f_hi:
        diagnostics.append(_lint_simple(
            "model_devi_f_trust_lo",
            "model_devi_f_trust_lo should be less than model_devi_f_trust_hi",
            "semantic consistency",
            text,
        ))

    numb_models = data.get("numb_models", 0)
    if numb_models > 0 and numb_models < 2:
        diagnostics.append(_lint_simple(
            "numb_models",
            "numb_models=1 may not be sufficient for model deviation. 4 is recommended.",
            "preflight/runtime-risk",
            text,
            severity="warning",
            blocking=False,
        ))

    if "fp_style" in data:
        fp_style = data["fp_style"]
        if fp_style in ("vasp", "pwscf", "abacus", "siesta"):
            fp_pp_files = data.get("fp_pp_files", [])
            if isinstance(fp_pp_files, list) and len(fp_pp_files) != type_map_len:
                diagnostics.append(_lint_simple(
                    "fp_pp_files",
                    f"fp_pp_files length ({len(fp_pp_files)}) should match type_map length ({type_map_len})",
                    "cross-file reference",
                    text,
                ))

    return diagnostics


def _lint_simple(
    key: str,
    message: str,
    category: str,
    text: str,
    severity: str = "error",
    blocking: bool = True,
) -> dict:
    line = 0
    character = 0
    length = len(key)
    lines = text.splitlines()
    for lno, raw in enumerate(lines):
        if f'"{key}"' in raw:
            line = lno
            character = raw.find(f'"{key}"')
            break
    return _diagnostic(line, character, message, severity, f"{key}.lint", length, category, blocking=blocking)