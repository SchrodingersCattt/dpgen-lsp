"""Tests for dpgen-lsp JSON path mapper."""


def test_json_path_mapper_basic():
    from dpgen_lsp.schema.json_path import JsonPathMapper

    text = '{\n  "type_map": ["H", "C"],\n  "numb_models": 4\n}'
    mapper = JsonPathMapper(text)
    assert mapper.get_path_at(1, 5) in ("type_map", "")
    assert mapper.get_path_at(2, 5) in ("numb_models", "")


def test_cursor_context():
    from dpgen_lsp.schema.json_path import JsonPathMapper

    text = '{\n  "type_map": ["H", "C"],\n  "numb_models": 4\n}'
    mapper = JsonPathMapper(text)
    ctx = mapper.get_cursor_context(1, 8)
    assert "line_text" in ctx
    assert "token" in ctx
    assert "before" in ctx
    assert "after" in ctx


def test_is_json():
    from dpgen_lsp.schema.json_path import is_json
    assert is_json('{"a": 1}')
    assert not is_json('not json')


def test_extract_full_path():
    from dpgen_lsp.schema.json_path import JsonPathMapper

    text = '{\n  "type_map": ["H"],\n  "numb_models": 4\n}'
    result = JsonPathMapper.extract_full_path(text, 1, 5)
    assert "type_map" in result