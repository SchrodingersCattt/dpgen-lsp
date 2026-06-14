"""Schema-driven JSON completion provider."""

from __future__ import annotations

from typing import Any

from ..schema.loader import load_schema_tree, detect_workflow
from ..schema.json_path import JsonPathMapper


def completion_items(text: str, line: int, character: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    mapper = JsonPathMapper(text)
    context = mapper.get_cursor_context(line, character)
    token = context.get("token", "")

    workflow = detect_workflow(text)
    schema = load_schema_tree(workflow)

    json_path = mapper.get_path_at(line, character)
    parent_node = schema.find_best_node(json_path)

    if parent_node is None:
        return _generic_completions(text, token)

    if parent_node.sub_fields:
        for name, child in parent_node.sub_fields.items():
            if token and token not in name:
                continue
            snippet = _completion_snippet(name, child)
            items.append({
                "label": name,
                "detail": _short_doc(child),
                "documentation": child.doc or f"Type: {child.json_type}",
                "kind": 9,
                "insertText": snippet,
                "insertTextFormat": 2,
            })

    if parent_node.sub_variants:
        for var in parent_node.sub_variants:
            for tag_name, tag_node in var.tags.items():
                if token and token not in tag_name:
                    continue
                items.append({
                    "label": tag_name,
                    "detail": f"variant option",
                    "documentation": tag_node.doc or var.doc,
                    "kind": 13,
                    "insertText": f'"{tag_name}"',
                    "insertTextFormat": 1,
                })

    if not items:
        items = _generic_completions(text, token)

    return items[:50]


def _short_doc(node) -> str:
    if not node.doc:
        return f"Type: {node.json_type}"
    doc = node.doc.replace("\n", " ")[:100]
    if not node.optional:
        doc = f"[required] {doc}"
    return doc


def _completion_snippet(name: str, node) -> str:
    if node.json_type == "string":
        return f'"{name}": "$1"'
    elif node.json_type == "integer":
        return f'"{name}": ${{1:0}}'
    elif node.json_type == "number":
        return f'"{name}": ${{1:0.0}}'
    elif node.json_type == "boolean":
        return f'"{name}": ${{1|true,false|}}'
    elif node.json_type == "array":
        return f'"{name}": [$1]'
    elif node.json_type == "object":
        return f'"{name}": {{\n\t$1\n}}'
    return f'"{name}": $1'


def _generic_completions(text: str, token: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for kw in ("type_map", "mass_map", "numb_models", "init_data_sys",
                "sys_configs", "model_devi_jobs", "fp_style", "fp_task_max",
                "fp_task_min", "default_training_param", "model_devi_dt",
                "model_devi_skip", "model_devi_f_trust_lo", "model_devi_f_trust_hi"):
        if not token or token in kw:
            items.append({"label": kw, "kind": 9, "detail": "dpgen parameter"})
    return items