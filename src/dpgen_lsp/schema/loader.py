"""Schema tree loader from dpgen arginfo definitions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .official_rules import machine_index, workflow_index

_SCHEMA_CACHE: dict[str, SchemaTree] = {}

DPGEN_WORKFLOWS = {
    "run": "dpgen.generator.arginfo",
    "simplify": "dpgen.simplify.arginfo",
    "init_bulk": "dpgen.data.arginfo",
    "init_surf": "dpgen.data.arginfo",
    "init_reaction": "dpgen.data.arginfo",
}

DPGEN_IMPORT_MAP = {
    "run": {
        "module": "dpgen.generator.arginfo",
        "func": "run_jdata_arginfo",
    },
    "simplify": {
        "module": "dpgen.simplify.arginfo",
        "func": "simplify_jdata_arginfo",
    },
    "init_bulk": {
        "module": "dpgen.data.arginfo",
        "func": "init_bulk_jdata_arginfo",
    },
    "init_surf": {
        "module": "dpgen.data.arginfo",
        "func": "init_surf_jdata_arginfo",
    },
    "init_reaction": {
        "module": "dpgen.data.arginfo",
        "func": "init_reaction_jdata_arginfo",
    },
}

MACHINE_IMPORT_MAP = {
    "module": "dpdispatcher.machine",
    "class": "Machine",
    "method": "arginfo",
}


@dataclass
class SchemaNode:
    name: str
    json_type: str
    default: Any = None
    optional: bool = True
    doc: str = ""
    alias: list[str] = field(default_factory=list)
    sub_fields: dict[str, SchemaNode] = field(default_factory=dict)
    sub_variants: list[VariantNode] = field(default_factory=list)
    is_list: bool = False
    list_item_type: str = ""
    list_item_node: SchemaNode | None = None
    variant_tags: list[str] = field(default_factory=list)
    node_type: str = "arg"
    path: str = ""


@dataclass
class VariantNode:
    name: str
    tags: dict[str, SchemaNode] = field(default_factory=dict)
    default_tag: str = ""
    optional: bool = True
    doc: str = ""


class SchemaTree:
    def __init__(self, workflow: str = "run"):
        self.workflow = workflow
        self.nodes: dict[str, SchemaNode] = {}
        self.root: SchemaNode | None = None
        self._load()

    def _load(self):
        info = DPGEN_IMPORT_MAP.get(self.workflow)
        if info is None:
            raise ValueError(f"Unknown workflow: {self.workflow}")

        try:
            module = _import_optional(info["module"])
            if module is None:
                self._load_static()
                return
            func = getattr(module, info["func"], None)
            if func is None:
                self._load_static()
                return
            arg = func()
            root_name = arg.name
            self.root = self._convert_argument(arg, parent_path="")
            self.root.name = root_name
            self.root.path = ""
            self._index_node(self.root, "")
        except Exception:
            self._load_static()

    def _load_static(self) -> None:
        index = workflow_index(self.workflow)
        fields = index.get("fields", {})
        if not fields:
            self.root = _fallback_schema_root(self.workflow)
            self._index_node(self.root, "")
            return

        root_name = index.get("root", f"{self.workflow}_jdata")
        root = SchemaNode(
            name=root_name,
            json_type="object",
            optional=False,
            doc=f"Static DP-GEN {self.workflow} schema derived from official documentation.",
            path="",
        )
        for name, meta in fields.items():
            node = SchemaNode(
                name=name,
                json_type=str(meta.get("json_type", "string")),
                default=meta.get("default"),
                optional=bool(meta.get("optional", True)),
                doc=str(meta.get("doc", "")),
                alias=list(meta.get("alias", []) or []),
                is_list=str(meta.get("json_type", "")) == "array",
                list_item_type=str(meta.get("list_item_type", "")),
                variant_tags=list(meta.get("variant_tags", []) or []),
                path=name,
            )
            root.sub_fields[name] = node
        self.root = root
        self._index_node(root, "")

    def _convert_argument(self, arg: Any, parent_path: str = "") -> SchemaNode:
        name = arg.name if hasattr(arg, "name") else ""
        current_path = f"{parent_path}.{name}" if parent_path else name

        json_type = self._infer_json_type(arg)
        is_list = self._is_list_type(arg)
        list_item_type = ""
        list_item_node = None

        if is_list:
            list_item_type = self._list_item_type_str(arg)
            if hasattr(arg, "sub_fields") and arg.sub_fields:
                list_item_node = SchemaNode(
                    name="[item]",
                    json_type="dict",
                    path=f"{current_path}[]",
                )
                for sub in arg.sub_fields:
                    child = self._convert_argument(sub, current_path)
                    list_item_node.sub_fields[child.name] = child

        sub_fields: dict[str, SchemaNode] = {}
        if hasattr(arg, "sub_fields") and arg.sub_fields:
            for sub in arg.sub_fields:
                child = self._convert_argument(sub, current_path)
                sub_fields[child.name] = child

        sub_variants: list[VariantNode] = []
        variant_tags: list[str] = []
        if hasattr(arg, "sub_variants") and arg.sub_variants:
            for var in arg.sub_variants:
                vn = self._convert_variant(var)
                sub_variants.append(vn)
                variant_tags.extend(vn.tags.keys())

        optional = getattr(arg, "optional", True)
        default = getattr(arg, "default", None)
        doc = getattr(arg, "doc", "")
        alias = list(getattr(arg, "alias", []) or [])

        return SchemaNode(
            name=name,
            json_type=json_type,
            default=default,
            optional=optional,
            doc=doc,
            alias=alias,
            sub_fields=sub_fields,
            sub_variants=sub_variants,
            is_list=is_list,
            list_item_type=list_item_type,
            list_item_node=list_item_node,
            variant_tags=variant_tags,
            node_type="arg",
            path=current_path,
        )

    def _convert_variant(self, var: Any) -> VariantNode:
        tags: dict[str, SchemaNode] = {}
        if hasattr(var, "flag_list") and var.flag_list:
            for arg in var.flag_list:
                child = self._convert_argument(arg, parent_path="")
                tags[child.name] = child
        return VariantNode(
            name=getattr(var, "name", ""),
            tags=tags,
            default_tag=getattr(var, "default_tag", ""),
            optional=getattr(var, "optional", True),
            doc=getattr(var, "doc", ""),
        )

    def _infer_json_type(self, arg: Any) -> str:
        dtype = getattr(arg, "dtype", None)
        if dtype is not None:
            name = getattr(dtype, "__name__", str(dtype))
            mapping = {
                "str": "string",
                "int": "integer",
                "float": "number",
                "bool": "boolean",
                "list": "array",
                "dict": "object",
            }
            return mapping.get(name, "string")
        return "string"

    def _is_list_type(self, arg: Any) -> bool:
        dtype = getattr(arg, "dtype", None)
        if dtype is not None:
            name = getattr(dtype, "__name__", str(dtype))
            return name == "list"
        return False

    def _list_item_type_str(self, arg: Any) -> str:
        repeat = getattr(arg, "repeat", None)
        if repeat and hasattr(repeat, "__name__"):
            mapping = {
                "str": "string",
                "int": "integer",
                "float": "number",
                "bool": "boolean",
            }
            return mapping.get(repeat.__name__, "string")
        return "string"

    def _index_node(self, node: SchemaNode, parent_path: str):
        self.nodes[node.path] = node
        for child in node.sub_fields.values():
            self._index_node(child, node.path)
        if node.list_item_node:
            self._index_node(node.list_item_node, node.path)

    def lookup(self, json_path: str) -> SchemaNode | None:
        return self.nodes.get(json_path)

    def find_node(self, json_path: str) -> SchemaNode | None:
        """Find an exact schema node for a JSON path.

        This compatibility wrapper is used by feature providers.  Variant
        fields are indexed as their argument names, so exact lookup is the
        desired behavior for hover and references. Static rule indexes also
        support a final-component fallback for nested JSON paths.
        """
        if not json_path:
            return self.root
        node = self.lookup(json_path)
        if node is not None:
            return node
        return self.lookup(json_path.rsplit(".", 1)[-1])

    def find_best_node(self, json_path: str) -> SchemaNode | None:
        """Find the best schema node for completion at a JSON path.

        Completion normally needs children of the current object. If an exact
        path is not indexed, walk upward through dotted path components and
        finally fall back to the root node.
        """
        if not json_path:
            return self.root
        parts = json_path.split(".")
        while parts:
            node = self.find_node(".".join(parts))
            if node is not None:
                return node
            parts.pop()
        return self.root

    def children_of(self, json_path: str) -> list[SchemaNode]:
        node = self.lookup(json_path)
        if node is None:
            return []
        return list(node.sub_fields.values())

    def to_json_schema(self) -> dict:
        if self.root is None:
            return {"type": "object", "properties": {}}

        def _to_json_schema(node: SchemaNode) -> dict:
            result: dict[str, Any] = {}
            if node.sub_fields:
                result["type"] = "object"
                props: dict[str, Any] = {}
                for name, child in node.sub_fields.items():
                    props[name] = _to_json_schema(child)
                result["properties"] = props
                required = [name for name, child in node.sub_fields.items() if not child.optional]
                if required:
                    result["required"] = required
                for var in node.sub_variants:
                    for tag_name, tag_node in var.tags.items():
                        props[var.name] = {
                            "type": "object",
                            "description": f"variant tag: {tag_name}",
                            "properties": {
                                k: _to_json_schema(v) for k, v in tag_node.sub_fields.items()
                            },
                        }
            elif node.json_type == "array":
                result["type"] = "array"
                result["items"] = {"type": node.list_item_type}
            else:
                result["type"] = node.json_type
            if not node.optional:
                result["$$required"] = True
            return result

        return _to_json_schema(self.root)


def load_schema_tree(workflow: str = "run") -> SchemaTree:
    if workflow not in _SCHEMA_CACHE:
        _SCHEMA_CACHE[workflow] = SchemaTree(workflow)
    return _SCHEMA_CACHE[workflow]


def _import_optional(module_name: str):
    try:
        from importlib import import_module

        return import_module(module_name)
    except Exception:
        return None


def _fallback_schema_root(workflow: str) -> SchemaNode:
    """Build a lightweight fallback schema when dpgen is unavailable.

    The authoritative schema still comes from DP-GEN's arginfo definitions when
    installed.  This fallback preserves useful completions, hovers, and tests in
    minimal environments.
    """
    root_name = {
        "run": "run_jdata",
        "simplify": "simplify_jdata",
        "init_bulk": "init_bulk_jdata",
        "init_surf": "init_surf_jdata",
        "init_reaction": "init_reaction_jdata",
    }.get(workflow, f"{workflow}_jdata")

    root = SchemaNode(name=root_name, json_type="object", optional=False, path="")

    def add(
        name: str,
        json_type: str,
        doc: str,
        optional: bool = True,
        default: Any = None,
        variant_tags: list[str] | None = None,
    ) -> None:
        root.sub_fields[name] = SchemaNode(
            name=name,
            json_type=json_type,
            optional=optional,
            default=default,
            doc=doc,
            path=name,
            is_list=json_type == "array",
            list_item_type="string" if json_type == "array" else "",
            variant_tags=variant_tags or [],
        )

    if workflow in {"init_bulk", "init_surf"}:
        add("stages", "array", f"Stages for dpgen {workflow}.", optional=False)
        add("elements", "array", "Chemical elements used to generate initial structures.", optional=False)
        add("potcars", "array", "VASP POTCAR paths in element order.")
        add("cell_type", "string", "Prototype cell type: fcc, hcp, bcc, sc, or diamond.")
        add("super_cell", "array", "Supercell replication, e.g. [2, 2, 2].", optional=False)
        add("from_poscar", "boolean", "Use an existing POSCAR/STRU instead of prototype cell generation.", default=False)
        add("from_poscar_path", "string", "Path to POSCAR or STRU when from_poscar is true.")
        add("relax_incar", "string", "Relaxation INCAR/INPUT path.")
        add("scale", "array", "Isotropic scaling factors.", optional=False)
        add("skip_relax", "boolean", "Skip the relaxation stage.", optional=False)
        add("pert_numb", "integer", "Number of perturbations for each scaled structure.", optional=False)
        add("pert_box", "number", "Cell perturbation amplitude.", optional=False)
        add("pert_atom", "number", "Atomic coordinate perturbation amplitude.", optional=False)
        add("coll_ndata", "integer", "Maximum collected data frames.", optional=False)
        if workflow == "init_bulk":
            add("type_map", "array", "Atom type names in DP-GEN order.")
            add("md_incar", "string", "AIMD INCAR/INPUT path.")
            add("md_nstep", "integer", "AIMD step count.", optional=False)
            add("init_fp_style", "string", "Initial-data FP backend: VASP or ABACUS.", variant_tags=["VASP", "ABACUS"])
        else:
            add("latt", "number", "Lattice constant for the unit cell.", optional=False)
            add("layer_numb", "integer", "Number of slab atom layers.")
            add("z_min", "integer", "Minimum slab thickness without vacuum.")
            add("vacuum_max", "number", "Maximum vacuum thickness.", optional=False)
            add("vacuum_min", "number", "Minimum vacuum thickness.")
            add("vacuum_resol", "array", "Vacuum thickness resolution.", optional=False)
            add("vacuum_numb", "integer", "Total number of vacuum layers.")
            add("mid_point", "number", "Mid point separating head and tail vacuum regions.")
            add("head_ratio", "number", "Ratio of vacuum layers in the nearby head region.")
            add("millers", "array", "Miller indices to generate.", optional=False)
        return root

    if workflow == "init_reaction":
        add("type_map", "array", "Atom types matching the initial reactive data.", optional=False)
        add("reaxff", "object", "ReaxFF NVT MD settings.", optional=False)
        add("cutoff", "number", "Cluster extraction cutoff radius.", optional=False)
        add("dataset_size", "integer", "Collected dataset size per bond type.", optional=False)
        add("qmkeywords", "string", "Gaussian force calculation keywords.", optional=False)
        return root

    add("type_map", "array", "Atom type names in DP-GEN order.", optional=False)
    add("mass_map", "array", "Atomic masses matching type_map order, or 'auto'.")
    add("init_data_prefix", "string", "Prefix for initial training data paths.")
    add("init_data_sys", "array", "Initial training data systems.", optional=False)
    add("sys_configs_prefix", "string", "Prefix for exploration structure paths.")
    add("sys_configs", "array", "2D list of structures used for exploration.", optional=False)
    add("numb_models", "integer", "Number of models to train. Four is recommended.", optional=False)
    add("default_training_param", "object", "DeePMD-kit training parameter template.", optional=False)
    add("model_devi_jobs", "array", "Exploration job settings for each iteration.", optional=False)
    add("model_devi_f_trust_lo", "number", "Lower force model-deviation trust bound.")
    add("model_devi_f_trust_hi", "number", "Upper force model-deviation trust bound.")
    if workflow == "simplify":
        fp_style_tags = [
            "none",
            "vasp",
            "gaussian",
            "siesta",
            "cp2k",
            "abacus",
            "pwmat",
            "pwscf",
            "custom",
        ]
    else:
        fp_style_tags = [
            "vasp",
            "gaussian",
            "siesta",
            "cp2k",
            "abacus",
            "amber/diff",
            "pwmat",
            "pwscf",
            "cpx",
            "custom",
        ]
    add("fp_style", "string", "First-principles engine.", optional=False, variant_tags=fp_style_tags)
    add("fp_task_max", "integer", "Maximum FP tasks selected per iteration.", optional=False)
    add("fp_task_min", "integer", "Minimum FP tasks required for next training iteration.", optional=False)
    add("fp_pp_path", "string", "Directory containing pseudopotential or basis files.")
    add("fp_pp_files", "array", "Pseudopotential files in type_map order.")
    add("fp_params", "object", "FP-backend-specific parameters.")

    if workflow == "simplify":
        add("pick_data", "array", "Dataset paths to simplify.", optional=False)
        add("init_pick_number", "integer", "Number of initially picked frames.", optional=False)
        add("iter_pick_number", "integer", "Number of frames picked per simplify iteration.", optional=False)
        add("labeled", "boolean", "Whether pick_data is already labeled.", default=False)

    return root


def load_machine_schema_tree() -> SchemaTree:
    schema = SchemaTree("run")
    index = machine_index()
    fields = index.get("fields", {})
    root = SchemaNode(
        name=str(index.get("root", "machine_jdata")),
        json_type="object",
        optional=False,
        doc="Static DP-GEN machine.json schema derived from official documentation.",
        path="",
    )
    for name, meta in fields.items():
        root.sub_fields[name] = SchemaNode(
            name=name,
            json_type=str(meta.get("json_type", "string")),
            default=meta.get("default"),
            optional=bool(meta.get("optional", True)),
            doc=str(meta.get("doc", "")),
            alias=list(meta.get("alias", []) or []),
            is_list=str(meta.get("json_type", "")) == "array",
            list_item_type=str(meta.get("list_item_type", "")),
            path=name,
        )
    schema.workflow = "machine"
    schema.nodes = {}
    schema.root = root
    schema._index_node(root, "")
    return schema


def detect_file_type(text: str) -> str:
    """Detect whether JSON text is a params.json or machine.json.

    machine.json structure:
    {
      "api_version": "1.0",
      "train": [ { "command": ..., "machine": {...}, "resources": {...} } ],
      "model_devi": [ ... ],
      "fp": [ ... ]
    }
    """
    try:
        data = json.loads(text)
        if "api_version" in data:
            return "machine"
        if isinstance(data.get("train"), list) and "type_map" not in data:
            return "machine"
        return "params"
    except json.JSONDecodeError:
        return "params"


def detect_workflow(text: str) -> str:
    try:
        data = json.loads(text)
        if "pick_data" in data and "iter_pick_number" in data:
            return "simplify"
        if "reaxff" in data and "dataset_size" in data:
            return "init_reaction"
        if "stages" in data and "millers" in data:
            return "init_surf"
        if "stages" in data and any(k in data for k in ("md_nstep", "init_fp_style", "md_incar")):
            return "init_bulk"
        if any(k in data for k in ("type_map", "numb_models", "model_devi_jobs")):
            return "run"
        return "run"
    except json.JSONDecodeError:
        return "run"
