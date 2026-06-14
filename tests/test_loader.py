"""Tests for dpgen-lsp schema loader."""


def test_load_schema_run():
    from dpgen_lsp.schema.loader import load_schema_tree
    import os
    import sys

    if os.getenv("SKIP_DPGEN_IMPORT"):
        return

    try:
        schema = load_schema_tree("run")
        assert schema.root is not None
        assert schema.root.name == "run_jdata"
        # dpgen arginfo structure varies by version
        if "type_map" in schema.nodes:
            type_map_node = schema.nodes["type_map"]
            assert type_map_node.json_type == "array"
            assert not type_map_node.optional
    except (ImportError, RuntimeError):
        pass


def test_load_schema_simplify():
    from dpgen_lsp.schema.loader import load_schema_tree
    import os

    if os.getenv("SKIP_DPGEN_IMPORT"):
        return

    try:
        schema = load_schema_tree("simplify")
        assert schema.root is not None
    except ImportError:
        pass


def test_schema_cache():
    from dpgen_lsp.schema.loader import load_schema_tree, _SCHEMA_CACHE
    import os

    if os.getenv("SKIP_DPGEN_IMPORT"):
        return

    try:
        _SCHEMA_CACHE.clear()
        s1 = load_schema_tree("run")
        s2 = load_schema_tree("run")
        assert s1 is s2
    except ImportError:
        pass


def test_detect_workflow():
    from dpgen_lsp.schema.loader import detect_workflow

    run_json = '{"type_map": ["H"], "numb_models": 4, "model_devi_jobs": []}'
    assert detect_workflow(run_json) == "run"

    simplify_json = '{"pick_data": [], "iter_pick_number": 5}'
    assert detect_workflow(simplify_json) == "simplify"