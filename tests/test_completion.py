"""Tests for dpgen-lsp completion provider."""


def test_completion_basic():
    from dpgen_lsp.features.completion import completion_items

    text = '{\n  ""\n}'
    items = completion_items(text, 1, 3)
    assert isinstance(items, list)
    assert len(items) > 0


def test_completion_fp_style():
    from dpgen_lsp.features.completion import completion_items

    text = '{\n  "fp_style": ""\n}'
    items = completion_items(text, 1, 16)
    assert isinstance(items, list)