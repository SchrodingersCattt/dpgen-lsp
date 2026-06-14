"""Schema tree loader from dpgen arginfo definitions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

_SCHEMA_CACHE: dict[str, SchemaTree] = {}

DPGEN_WORKFLOWS = {
    "run": "dpgen.generator.arginfo",
    "simplify": "dpgen.simplify.arginfo",
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
                return
            func = getattr(module, info["func"], None)
            if func is None:
                return
            arg = func()
            root_name = arg.name
            self.root = self._convert_argument(arg, parent_path="")
            self.root.name = root_name
            self.root.path = ""
            self._index_node(self.root, "")
        except Exception as e:
            raise RuntimeError(f"Failed to load dpgen arginfo: {e}") from e

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

    def _index_node(self, node: SchemaNode, parent_path: str):
        key = node.path if node.path else parent_path
        if key:
            self.nodes[key] = node
        for child in node.sub_fields.values():
            self._index_node(child, child.path)
        for var in node.sub_variants:
            for tag, child in var.tags.items():
                self._index_node(child, child.path)

    @staticmethod
    def _infer_json_type(arg: Any) -> str:
        type_info = getattr(arg, "dtype", None)
        if type_info is None:
            return "any"
        type_str = str(type_info)
        mapping = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "dict": "object",
            "list": "array",
            "NoneType": "null",
        }
        for py_type, json_type in mapping.items():
            if py_type in type_str:
                return json_type
        return "any"

    @staticmethod
    def _is_list_type(arg: Any) -> bool:
        type_info = getattr(arg, "dtype", None)
        if type_info is None:
            return False
        type_str = str(type_info)
        return "list" in type_str

    @staticmethod
    def _list_item_type_str(arg: Any) -> str:
        type_info = getattr(arg, "dtype", None)
        if type_info is None:
            return "any"
        type_str = str(type_info)
        if "str" in type_str:
            return "string"
        if "int" in type_str:
            return "integer"
        if "float" in type_str:
            return "number"
        if "bool" in type_str:
            return "boolean"
        if "dict" in type_str:
            return "object"
        if "list[list" in type_str:
            return "array"
        return "any"

    def find_node(self, json_path: str) -> SchemaNode | None:
        # Search by exact path
        node = self.nodes.get(json_path)
        if node is not None:
            return node
        # Search by name (for short key lookups)
        for n in self.nodes.values():
            if n.name == json_path:
                return n
        return None

    def find_best_node(self, json_path: str) -> SchemaNode | None:
        node = self.nodes.get(json_path)
        if node is not None:
            return node
        parts = json_path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            parent = ".".join(parts[:i])
            node = self.nodes.get(parent)
            if node is not None and node.sub_fields:
                return node
        return self.root

    def get_completions(self, json_path: str) -> list[dict[str, str]]:
        node = self.nodes.get(json_path)
        if node is None:
            node = self.root

        items: list[dict[str, str]] = []

        if node and node.sub_fields:
            for name, child in node.sub_fields.items():
                items.append({
                    "label": name,
                    "detail": child.doc[:80] if child.doc else child.json_type,
                    "kind": "property",
                })

        if node and node.sub_variants:
            for var in node.sub_variants:
                items.append({
                    "label": var.name,
                    "detail": f"variant: {', '.join(var.tags.keys())}",
                    "kind": "enum",
                })

        return items

    def get_hover(self, json_path: str) -> str:
        node = self.nodes.get(json_path)
        if node is None:
            return ""
        parts = []
        parts.append(f"**{node.name}** ({node.json_type})")
        if not node.optional:
            parts.append("*required*")
        else:
            parts.append(f"*optional*, default: {node.default!r}")
        if node.doc:
            parts.append("")
            parts.append(node.doc)
        if node.alias:
            parts.append("")
            parts.append(f"Alias: {', '.join(node.alias)}")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        if self.root is None:
            return {}

        def _node_to_dict(node: SchemaNode) -> dict:
            result: dict[str, Any] = {
                "name": node.name,
                "type": node.json_type,
                "optional": node.optional,
                "doc": node.doc,
            }
            if node.sub_fields:
                result["properties"] = {
                    k: _node_to_dict(v) for k, v in node.sub_fields.items()
                }
            if node.sub_variants:
                result["variants"] = [
                    {
                        "name": v.name,
                        "tags": list(v.tags.keys()),
                        "default": v.default_tag,
                    }
                    for v in node.sub_variants
                ]
            if node.is_list:
                result["items"] = {"type": node.list_item_type}
            return result

        return _node_to_dict(self.root)

    def to_json_schema(self) -> dict:
        if self.root is None:
            return {}

        def _to_json_schema(node: SchemaNode) -> dict:
            result: dict[str, Any] = {"description": node.doc or node.name}
            if node.json_type == "object":
                result["type"] = "object"
                props = {}
                required = []
                for k, v in node.sub_fields.items():
                    props[k] = _to_json_schema(v)
                    if not v.optional:
                        required.append(k)
                if props:
                    result["properties"] = props
                if required:
                    result["required"] = required
                for var in node.sub_variants:
                    for tag_name, tag_node in var.tags.items():
                        props[var.name] = {
                            "type": "object",
                            "description": f"variant tag: {tag_name}",
                            "properties": {
                                k: _to_json_schema(v)
                                for k, v in tag_node.sub_fields.items()
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


def detect_workflow(text: str) -> str:
    try:
        data = json.loads(text)
        if any(k in data for k in ("type_map", "numb_models", "model_devi_jobs")):
            return "run"
        if "pick_data" in data and "iter_pick_number" in data:
            return "simplify"
        return "run"
    except json.JSONDecodeError:
        return "run"