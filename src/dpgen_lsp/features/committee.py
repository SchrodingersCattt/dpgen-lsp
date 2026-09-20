"""DP-GEN 0.14 committee and DPA compatibility checks."""

from __future__ import annotations

from typing import Any


BACKENDS = {
    "tensorflow": {"formats": {"pb"}, "default": "pb"},
    "pytorch": {"formats": {"pth", "pt2"}, "default": "pth"},
    "pytorch-exportable": {"formats": {"pte", "pt2"}, "default": "pte"},
    "jax": {"formats": {"savedmodel"}, "default": "savedmodel"},
}


def _backend(value: Any) -> str:
    value = str(value or "tensorflow").lower()
    return "pytorch-exportable" if value in {"pt-expt", "pytorch_exportable"} else value


def _sections(training: dict[str, Any]) -> list[dict[str, Any]]:
    model = training.get("model") or {}
    branches = model.get("model_dict") or {}
    return list(branches.values()) if isinstance(branches, dict) and branches else [model]


def _resolve(model: dict[str, Any], key: str, shared: dict[str, Any]) -> Any:
    value = model.get(key)
    if not isinstance(value, str):
        return value
    return shared.get(value.split(":", 1)[0], value)


def family(training: dict[str, Any]) -> str | None:
    families: set[str] = set()
    for model in _sections(training):
        model_type = str(model.get("type", "")).lower()
        descriptor = model.get("descriptor") or {}
        if isinstance(descriptor, str):
            descriptor = (training.get("model") or {}).get("shared_dict", {}).get(
                descriptor.split(":", 1)[0], {}
            )
        descriptor_type = str(descriptor.get("type", "")).lower() if isinstance(descriptor, dict) else ""
        if descriptor_type == "dpa4c":
            families.add("dpa4c")
        if model_type in {"dpa4", "sezm"} or descriptor_type in {"dpa4", "sezm"}:
            families.add("dpa4")
    return "mixed" if len(families) > 1 else next(iter(families), None)


def _cutoff(descriptor: dict[str, Any]) -> Any:
    dtype = str(descriptor.get("type", "")).lower()
    if dtype == "dpa2":
        return (descriptor.get("repinit") or {}).get("rcut")
    if dtype == "dpa3":
        return (descriptor.get("repflow") or {}).get("e_rcut")
    return descriptor.get("rcut")


def signature(training: dict[str, Any], global_type_map: list[Any]) -> tuple[Any, ...]:
    model = training.get("model") or {}
    shared = model.get("shared_dict") or {}
    type_maps: set[tuple[Any, ...]] = set()
    cutoffs: set[Any] = set()
    outputs: set[Any] = set()
    fparams: set[Any] = set()
    aparams: set[Any] = set()
    for branch in _sections(training):
        type_map = _resolve(branch, "type_map", shared)
        type_maps.add(tuple(type_map if isinstance(type_map, list) else global_type_map))
        descriptor = _resolve(branch, "descriptor", shared) or {}
        cutoffs.add(_cutoff(descriptor) if isinstance(descriptor, dict) else None)
        fitting = _resolve(branch, "fitting_net", shared) or {}
        if isinstance(fitting, dict):
            outputs.add(fitting.get("type", "ener"))
            fparams.add(fitting.get("numb_fparam", 0) or 0)
            aparams.add(fitting.get("numb_aparam", 0) or 0)
        else:
            outputs.add("ener" if str(branch.get("type", "")).lower() in {"dpa2", "dpa3", "dpa4", "dpa4c", "sezm"} else branch.get("type"))
    return tuple(map(lambda x: tuple(sorted(x, key=repr)), (type_maps, cutoffs, outputs, fparams, aparams)))


def validate(data: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    params = data.get("default_training_param", {})
    numb_models = data.get("numb_models", 0)
    if isinstance(params, list):
        if len(params) != numb_models:
            issues.append({"code": "committee.length", "message": f"default_training_param has {len(params)} members but numb_models is {numb_models}."})
        if not all(isinstance(item, dict) for item in params):
            issues.append({"code": "committee.member_type", "message": "Every committee member must be an object."})
        members = [item for item in params if isinstance(item, dict)]
    elif isinstance(params, dict):
        members = [params]
    else:
        return [{"code": "committee.member_type", "message": "default_training_param must be an object or list of objects."}]

    backend = _backend(data.get("train_backend"))
    model_format = data.get("model_format")
    engine = str(data.get("model_devi_engine", "lammps")).lower()
    if backend not in BACKENDS:
        issues.append({"code": "model.backend.incompatible", "message": f"Unsupported train_backend '{backend}'."})
        return issues
    if model_format is not None and model_format not in BACKENDS[backend]["formats"]:
        issues.append({"code": "model.format.incompatible", "message": f"model_format '{model_format}' is not supported by backend '{backend}'."})
    if backend == "pytorch-exportable" and model_format == "pte" and engine == "lammps":
        issues.append({"code": "model.format.incompatible", "message": "LAMMPS model deviation requires model_format='pt2', not 'pte'."})

    families = [family(item) for item in members]
    if "mixed" in families or ("dpa4" in families and "dpa4c" in families):
        issues.append({"code": "model.family.mixed", "message": "DPA4 and DPA4C branches cannot share one committee."})
    if "dpa4" in families and backend != "pytorch":
        issues.append({"code": "model.backend.incompatible", "message": "DPA4 requires train_backend='pytorch'."})
    if "dpa4c" in families and backend != "pytorch-exportable":
        issues.append({"code": "model.backend.incompatible", "message": "DPA4C requires train_backend='pytorch-exportable' or 'pt-expt'."})
    if ("dpa4" in families or "dpa4c" in families) and engine == "lammps" and model_format not in {None, "pt2"}:
        issues.append({"code": "model.format.incompatible", "message": "DPA4/DPA4C LAMMPS model deviation requires model_format='pt2'."})
    if backend == "pytorch" and model_format == "pt2" and all(item_family is None for item_family in families):
        issues.append({"code": "model.format.incompatible", "message": "Regular PyTorch models cannot use pt2; pt2 is reserved for DPA4/SeZM."})

    for item, item_family in zip(members, families):
        for scope, model in [("model", branch) for branch in _sections(item)]:
            if item_family == "dpa4c" and any(key in model for key in ("use_compile", "enable_tf32")):
                issues.append({"code": "model.compile_scope", "message": "DPA4C compile options belong under training, not model."})
            if item_family == "dpa4" and any(key in (item.get("training") or {}) for key in ("use_compile", "enable_tf32")):
                issues.append({"code": "model.compile_scope", "message": "DPA4 compile options belong under model, not training."})

    if isinstance(params, list) and members:
        reference = signature(members[0], data.get("type_map", []))
        for index, member in enumerate(members[1:], start=1):
            current = signature(member, data.get("type_map", []))
            for code, label, expected, actual in zip(
                ("committee.type_map", "committee.cutoff", "committee.output_class", "committee.fparam_dimension", "committee.aparam_dimension"),
                ("type map", "cutoff", "output class", "fparam dimensions", "aparam dimensions"),
                reference,
                current,
            ):
                if expected != actual:
                    issues.append({"code": code, "message": f"Committee member {index} has incompatible {label}."})
        if model_format == "pt2":
            lower_kinds = {"graph" if item_family in {"dpa4", "dpa4c"} else "nlist" for item_family in families}
            if len(lower_kinds) > 1:
                issues.append({"code": "committee.pt2_lower_kind", "message": "PT2 committee members must use the same lower kind (graph or nlist)."})
    return issues
