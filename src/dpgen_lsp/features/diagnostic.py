"""Diagnostics provider for JSON parse and schema validation."""

from __future__ import annotations

import json
from glob import glob
from pathlib import Path
from typing import Any

from ..schema.loader import (
    SchemaTree,
    load_schema_tree,
    detect_workflow,
    detect_file_type,
    DPGEN_IMPORT_MAP,
)
from ..schema.official_rules import manual_ref_for

# PR4: Bohrium machine type whitelist
KNOWN_BOHRIUM_MACHINES = {
    "cpu": [
        "c2_m4_cpu",
        "c4_m8_cpu",
        "c8_m16_cpu",
        "c16_m32_cpu",
        "c32_m64_cpu",
        "c32_m128_cpu",
        "c64_m256_cpu",
    ],
    "gpu": [
        "1 * NVIDIA V100_32g",
        "1 * NVIDIA A100_80g",
        "1 * NVIDIA 4090",
        "2 * NVIDIA V100_32g",
        "2 * NVIDIA A100_80g",
        "4 * NVIDIA A100_80g",
    ],
}


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
    manual_ref: str | None = None,
    expected: Any = None,
    actual: Any = None,
) -> dict:
    payload = {
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
    if manual_ref:
        payload["manual_ref"] = manual_ref
    if expected is not None:
        payload["expected"] = expected
    if actual is not None:
        payload["actual"] = actual
    return payload


class DiagnosticProvider:

    def __init__(self):
        self._schema_cache: dict[str, SchemaTree] = {}

    def get_diagnostics(self, text: str, uri: str = "", base_dir: Path | None = None) -> list[dict]:
        diagnostics: list[dict] = []

        if not text.strip():
            return diagnostics

        try:
            json.loads(text)
        except json.JSONDecodeError as e:
            diagnostics.append(
                _diagnostic(
                    e.lineno - 1 if e.lineno else 0,
                    e.colno - 1 if e.colno else 0,
                    f"JSON parse error: {e.msg}",
                    severity="error",
                    code="json.parse_error",
                    category="syntax",
                )
            )
            return diagnostics

        try:
            data = json.loads(text)
        except Exception:
            return diagnostics

        file_type = detect_file_type(text)

        if file_type == "machine":
            diagnostics.extend(_lint_machine_sections(data, text))
            diagnostics.extend(_validate_machine_config(data, text))
        else:
            workflow = detect_workflow(text)
            schema = self._get_schema(workflow)
            if schema.root is not None:
                try:
                    info = DPGEN_IMPORT_MAP[schema.workflow]
                    arginfo_module = __import__(info["module"], fromlist=[info["func"]])
                    arginfo_func = getattr(arginfo_module, info["func"])
                    arg = arginfo_func()
                    arg.check_value(data, strict=False)
                except ImportError:
                    pass
                except Exception as e:
                    diagnostics.append(
                        _diagnostic(
                            0,
                            0,
                            f"Schema validation: {e}",
                            severity="error",
                            code="schema.validation",
                            category="schema",
                            manual_ref=manual_ref_for(workflow, code="schema.validation"),
                        )
                    )

            # PR2: CP2K FP semantic lint
            diagnostics.extend(_lint_cp2k_fp(data, text))

        # General lint checks
        diagnostics.extend(_lint_checks(data, text))

        # PR3: Path existence preflight
        if base_dir is not None:
            diagnostics.extend(_lint_path_existence(data, text, base_dir))

        return diagnostics

    def _get_schema(self, workflow: str) -> SchemaTree:
        if workflow not in self._schema_cache:
            try:
                self._schema_cache[workflow] = load_schema_tree(workflow)
            except Exception:
                self._schema_cache[workflow] = SchemaTree(workflow)
        return self._schema_cache[workflow]


# ── PR1: machine.json schema validation ──────────────────────────────────


def _validate_machine_config(data: dict, text: str) -> list[dict]:
    """Validate machine.json sections against dpdispatcher Machine.arginfo().

    machine.json structure:
    {
      "train": [ { "machine": {...}, ... } ],
      "model_devi": [ { "machine": {...}, ... } ],
      "fp": [ { "machine": {...}, ... } ]
    }
    """
    diagnostics: list[dict] = []

    try:
        from dpdispatcher.machine import Machine

        machine_arginfo = Machine.arginfo()
    except ImportError:
        return diagnostics
    except Exception:
        return diagnostics

    for section_name in ("train", "model_devi", "fp"):
        section_data = data.get(section_name)
        tasks: list[dict] = []
        if isinstance(section_data, dict):
            tasks = [section_data]  # canonical
        elif isinstance(section_data, list):
            tasks = section_data    # deprecated list-form—warning already emitted by _lint_machine_sections
        else:
            continue

        for idx, task in enumerate(tasks):
            if not isinstance(task, dict):
                continue
            machine_data = task.get("machine")
            if machine_data is None or not isinstance(machine_data, dict):
                continue

            try:
                machine_arginfo.check_value(machine_data, strict=False)
            except Exception as e:
                err_msg = str(e)
                line = _find_section_line(text, section_name)
                fix_hints = []
                if "program_id" in err_msg:
                    fix_hints.append("Change program_id from string to integer")
                if "remote_profile" in err_msg:
                    fix_hints.append(
                        "Ensure remote_profile contains email, password, and program_id"
                    )
                diagnostics.append(
                    _diagnostic(
                        line,
                        0,
                        f"Machine config validation error in '{section_name}': {err_msg}",
                        severity="error",
                        code=f"machine.{section_name}.schema",
                        category="schema",
                        fix_hints=fix_hints,
                    )
                )

    # PR4: scass_type whitelist check
    diagnostics.extend(_lint_machine_type_whitelist(data, text))

    return diagnostics


# ── PR2: CP2K FP semantic lint ───────────────────────────────────────────


def _lint_cp2k_fp(data: dict, text: str) -> list[dict]:
    """Check CP2K-specific fp_params for common issues."""
    diagnostics: list[dict] = []

    fp_style = data.get("fp_style")
    if fp_style != "cp2k":
        return diagnostics

    fp_params = data.get("fp_params", {})
    if not isinstance(fp_params, dict):
        return diagnostics

    # Check PRINT_LEVEL — must be MEDIUM for dpdata parsing
    global_params = fp_params.get("GLOBAL", {})
    if isinstance(global_params, dict):
        print_level = global_params.get("PRINT_LEVEL", "MEDIUM")
        if print_level != "MEDIUM":
            line = _find_key_line(text, "PRINT_LEVEL")
            diagnostics.append(
                _diagnostic(
                    line,
                    0,
                    f"CP2K PRINT_LEVEL is '{print_level}', must be 'MEDIUM' "
                    f"for dpdata to parse AIMD output. "
                    f"cp2kdata raises on PRINT_LEVEL LOW.",
                    severity="error",
                    code="PRINT_LEVEL.lint",
                    category="preflight/runtime-risk",
                    fix_hints=["Set fp_params.GLOBAL.PRINT_LEVEL to 'MEDIUM'"],
                    manual_ref=manual_ref_for("run", code="PRINT_LEVEL.lint"),
                    expected="MEDIUM",
                    actual=print_level,
                )
            )

    # Check STRESS_TENSOR in MOTION%PRINT
    motion_print = fp_params.get("MOTION", {}).get("PRINT", {})
    if isinstance(motion_print, dict):
        has_stress = "STRESS_TENSOR" in motion_print
        if not has_stress:
            line = _find_key_line(text, "fp_params")
            diagnostics.append(
                _diagnostic(
                    line,
                    0,
                    "CP2K fp_params missing MOTION%PRINT%STRESS_TENSOR. "
                    "Virial/stress data will not be collected.",
                    severity="warning",
                    code="STRESS_TENSOR.lint",
                    category="preflight/runtime-risk",
                    fix_hints=[
                        "Add &STRESS_TENSOR subsection under &MOTION/&PRINT " "with EACH {MD} 1"
                    ],
                    blocking=False,
                    manual_ref=manual_ref_for("run", code="STRESS_TENSOR.lint"),
                )
            )

    return diagnostics


# ── PR3: Path existence preflight ────────────────────────────────────────


def _lint_path_existence(data: dict, text: str, base_dir: Path) -> list[dict]:
    """Check that referenced paths (init_data_sys, sys_configs) exist."""
    diagnostics: list[dict] = []

    # init_data_sys — required for training
    init_data_sys = data.get("init_data_sys", [])
    if isinstance(init_data_sys, list):
        for i, p in enumerate(init_data_sys):
            if not isinstance(p, str):
                continue
            resolved = base_dir / p
            if not _path_or_glob_exists(resolved):
                line = _find_key_line(text, "init_data_sys")
                diagnostics.append(
                    _diagnostic(
                        line,
                        0,
                        f"init_data_sys[{i}] path does not exist: {p} " f"(resolved to {resolved})",
                        severity="error",
                        code="path.init_data_sys",
                        category="cross-file reference",
                        fix_hints=[
                            f"Create directory '{p}' or run AIMD to generate training data first"
                        ],
                        manual_ref=manual_ref_for("run", code="path.init_data_sys"),
                    )
                )

    # sys_configs — required for exploration
    sys_configs = data.get("sys_configs", [])
    for i, p in enumerate(_iter_string_paths(sys_configs)):
        resolved = base_dir / p
        if not _path_or_glob_exists(resolved):
            line = _find_key_line(text, "sys_configs")
            diagnostics.append(
                _diagnostic(
                    line,
                    0,
                    f"sys_configs[{i}] path does not exist: {p} " f"(resolved to {resolved})",
                    severity="error",
                    code="path.sys_configs",
                    category="cross-file reference",
                    fix_hints=[f"Create POSCAR file at '{p}' or update the path"],
                    manual_ref=manual_ref_for("run", code="path.sys_configs"),
                )
            )

    return diagnostics


def _iter_string_paths(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        paths: list[str] = []
        for item in value:
            paths.extend(_iter_string_paths(item))
        return paths
    return []


def _path_or_glob_exists(path: Path) -> bool:
    text = str(path)
    if any(ch in text for ch in "*?["):
        return bool(glob(text))
    return path.exists()


# ── PR4: Bohrium machine type whitelist ──────────────────────────────────


def _lint_machine_type_whitelist(data: dict, text: str) -> list[dict]:
    """Warn if scass_type doesn't match known Bohrium machine types."""
    diagnostics: list[dict] = []

    all_known = set()
    for types in KNOWN_BOHRIUM_MACHINES.values():
        all_known.update(types)

    # Track which scass_type occurrences we've already reported
    used_lines: set[int] = set()

    # machine.json: train/model_devi/fp are dict (canonical) or list (deprecated)
    for section_name in ("train", "model_devi", "fp"):
        section_data = data.get(section_name)
        tasks: list[dict] = []
        if isinstance(section_data, dict):
            tasks = [section_data]
        elif isinstance(section_data, list):
            tasks = section_data
        else:
            continue

        for task in tasks:
            if not isinstance(task, dict):
                continue
            # Check machine.remote_profile.input_data.scass_type
            machine = task.get("machine", {})
            if not isinstance(machine, dict):
                continue
            remote_profile = machine.get("remote_profile", {})
            if not isinstance(remote_profile, dict):
                continue
            input_data = remote_profile.get("input_data", {})
            if not isinstance(input_data, dict):
                continue
            scass_type = input_data.get("scass_type")
            if isinstance(scass_type, str) and scass_type not in all_known:
                line = _find_next_key_line(text, "scass_type", used_lines)
                used_lines.add(line)
                known_list = ", ".join(sorted(all_known))
                diagnostics.append(
                    _diagnostic(
                        line,
                        0,
                        f"scass_type '{scass_type}' not in known Bohrium machine types. "
                        f"Known types: {known_list}",
                        severity="warning",
                        code=f"machine.{section_name}.scass_type",
                        category="preflight/runtime-risk",
                        fix_hints=["Check available machine types via Bohrium API"],
                        blocking=False,
                        manual_ref=manual_ref_for(
                            "machine",
                            code=f"machine.{section_name}.scass_type",
                            field="scass_type",
                        ),
                        expected=sorted(all_known),
                        actual=scass_type,
                    )
                )

    return diagnostics


def _lint_machine_sections(data: dict, text: str) -> list[dict]:
    diagnostics: list[dict] = []
    for section_name in ("train", "model_devi", "fp"):
        if section_name not in data:
            diagnostics.append(
                _diagnostic(
                    0,
                    0,
                    f"machine.json missing required top-level section '{section_name}'. "
                    "DP-GEN run machine.json is composed of train, model_devi, and fp parts.",
                    severity="error",
                    code="machine.section.missing",
                    category="schema",
                    fix_hints=[f"Add top-level '{section_name}': {{}} section"],
                    manual_ref=manual_ref_for("machine", code="machine.section.missing"),
                    expected="dict (canonical) or list (deprecated compat)",
                    actual="missing",
                )
            )
            continue
        section_val = data.get(section_name)
        if isinstance(section_val, dict):
            # canonical format: {"train": {"command": ..., "machine": ..., "resources": ...}}
            continue
        if isinstance(section_val, list):
            # deprecated list-form for backward compat — warn, non-blocking
            line = _find_key_line(text, section_name)
            diagnostics.append(
                _diagnostic(
                    line,
                    0,
                    f"machine.json section '{section_name}' is a list. "
                    "List-form is deprecated in DP-GEN; use a dict task object instead "
                    "(e.g. {{\"command\": ..., \"machine\": ..., \"resources\": ...}}). "
                    "DP-GEN still converts lists via convert_mdata() for backward compat, "
                    "but external tooling validates the canonical dict schema.",
                    severity="warning",
                    code="machine.section.deprecated_list",
                    category="best-practice/deprecation",
                    fix_hints=[
                        f"Change '{section_name}' from a list to a single dict task object"
                    ],
                    manual_ref=manual_ref_for(
                        "machine", code="machine.section.deprecated_list"
                    ),
                    expected="dict",
                    actual="list (deprecated)",
                    blocking=False,
                )
            )
            continue
        # scalar or other type
        line = _find_key_line(text, section_name)
        diagnostics.append(
            _diagnostic(
                line,
                0,
                f"machine.json section '{section_name}' must be a dict (canonical) "
                "or list (deprecated) of task environments.",
                severity="error",
                code="machine.section.type",
                category="type/value",
                fix_hints=[
                    f"Change '{section_name}' to a dict task object: "
                    '{"command": "...", "machine": {...}, "resources": {...}}'
                ],
                manual_ref=manual_ref_for("machine", code="machine.section.type"),
                expected="dict or list",
                actual=type(section_val).__name__,
            )
        )
    return diagnostics


# ── General lint checks ──────────────────────────────────────────────────


def _lint_checks(data: dict, text: str) -> list[dict]:
    diagnostics: list[dict] = []

    type_map_len = len(data.get("type_map", []))
    mass_map_val = data.get("mass_map", [])
    if (
        isinstance(mass_map_val, list)
        and mass_map_val != "auto"
        and len(mass_map_val) != type_map_len
    ):
        diagnostics.append(
            _lint_simple(
                "mass_map",
                "mass_map length should match type_map length",
                "type/value",
                text,
            )
        )

    fp_task_max = data.get("fp_task_max", 0)
    fp_task_min = data.get("fp_task_min", 0)
    if fp_task_max > 0 and fp_task_min > 0 and fp_task_max < fp_task_min:
        diagnostics.append(
            _lint_simple(
                "fp_task_max",
                "fp_task_max should be >= fp_task_min",
                "type/value",
                text,
            )
        )

    f_lo = data.get("model_devi_f_trust_lo", 0)
    f_hi = data.get("model_devi_f_trust_hi", 1)
    if isinstance(f_lo, (int, float)) and isinstance(f_hi, (int, float)) and f_lo >= f_hi:
        diagnostics.append(
            _lint_simple(
                "model_devi_f_trust_lo",
                "model_devi_f_trust_lo should be less than model_devi_f_trust_hi",
                "semantic consistency",
                text,
            )
        )

    numb_models = data.get("numb_models", 0)
    if numb_models > 0 and numb_models < 2:
        diagnostics.append(
            _lint_simple(
                "numb_models",
                "numb_models=1 may not be sufficient for model deviation. 4 is recommended.",
                "preflight/runtime-risk",
                text,
                severity="warning",
                blocking=False,
            )
        )

    if "fp_style" in data:
        fp_style = data["fp_style"]
        if fp_style in ("vasp", "pwscf", "abacus", "siesta"):
            fp_pp_files = data.get("fp_pp_files", [])
            if isinstance(fp_pp_files, list) and len(fp_pp_files) != type_map_len:
                diagnostics.append(
                    _lint_simple(
                        "fp_pp_files",
                        f"fp_pp_files length ({len(fp_pp_files)}) should match type_map length ({type_map_len})",
                        "cross-file reference",
                        text,
                    )
                )

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
    return _diagnostic(
        line,
        character,
        message,
        severity,
        f"{key}.lint",
        length,
        category,
        blocking=blocking,
        manual_ref=manual_ref_for("run", field=key, code=f"{key}.lint"),
    )


def _find_key_line(text: str, key: str) -> int:
    """Find the line number of a key in JSON text."""
    lines = text.splitlines()
    for lno, raw in enumerate(lines):
        if f'"{key}"' in raw:
            return lno
    return 0


def _find_next_key_line(text: str, key: str, used_lines: set[int]) -> int:
    """Find the next unused occurrence of a key in JSON text."""
    lines = text.splitlines()
    for lno, raw in enumerate(lines):
        if f'"{key}"' in raw and lno not in used_lines:
            return lno
    return 0


def _find_section_line(text: str, section_name: str) -> int:
    """Find the line number of a top-level section key."""
    lines = text.splitlines()
    for lno, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.startswith(f'"{section_name}"'):
            return lno
    return 0
