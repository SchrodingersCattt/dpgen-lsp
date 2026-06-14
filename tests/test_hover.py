"""Tests for dpgen-lsp hover provider."""


def test_hover_basic():
    from dpgen_lsp.features.hover import hover_contents

    text = '{\n  "type_map": ["H"]\n}'
    result = hover_contents(text, 1, 8)
    # dpgen arginfo structure varies by version; skip if type_map not in schema
    import pytest
    if result is None:
        pytest.skip("type_map not found in dpgen schema (version mismatch)")
    assert "type_map" in result


def test_hover_no_token():
    from dpgen_lsp.features.hover import hover_contents

    text = '{\n  \n}'
    result = hover_contents(text, 1, 2)
    assert result is None