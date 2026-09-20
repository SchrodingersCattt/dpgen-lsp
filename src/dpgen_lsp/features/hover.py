"""Schema-driven JSON hover provider."""

from ..schema.loader import load_schema_tree, detect_workflow
from ..schema.json_path import JsonPathMapper


def hover_contents(text: str, line: int, character: int) -> str | None:
    mapper = JsonPathMapper(text)
    context = mapper.get_cursor_context(line, character)
    token = context.get("token", "")

    if not token:
        return None

    workflow = detect_workflow(text)
    schema = load_schema_tree(workflow)

    json_path = mapper.get_path_at(line, character)
    if not json_path:
        return None

    node = schema.find_node(json_path)
    if node is None:
        return None

    parts = []
    parts.append(f"```json\n\"{node.name}\": <{node.json_type}>\n```")
    parts.append("")
    if not node.optional:
        parts.append("**Required**")
    else:
        default_str = repr(node.default) if node.default is not None else "—"
        parts.append(f"Optional, default: `{default_str}`")
    if node.doc:
        parts.append("")
        parts.append(node.doc)
    if node.alias:
        parts.append("")
        parts.append(f"Aliases: {', '.join(node.alias)}")

    if node.name == "default_training_param":
        parts.extend(["", "DP-GEN 0.14.0 accepts an object or a list of exactly `numb_models` committee objects.", "Committee members must agree on type map, cutoff, output class, fparam/aparam dimensions, and PT2 lower kind."])
    elif node.name == "train_backend":
        parts.extend(["", "DPA4 uses `pytorch`; DPA4C uses `pytorch-exportable` (alias `pt-expt`)."])
    elif node.name == "model_format":
        parts.extend(["", "LAMMPS model deviation for DPA4/DPA4C uses `pt2`; `pte` is not supported by LAMMPS."])

    return "\n".join(parts)
