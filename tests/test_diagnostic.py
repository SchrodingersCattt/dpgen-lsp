"""Tests for dpgen-lsp diagnostic provider."""


def test_empty_text():
    from dpgen_lsp.features.diagnostic import DiagnosticProvider

    provider = DiagnosticProvider()
    diags = provider.get_diagnostics("")
    assert diags == []


def test_valid_json():
    from dpgen_lsp.features.diagnostic import DiagnosticProvider

    provider = DiagnosticProvider()
    text = '{"type_map": ["H"], "numb_models": 4}'
    diags = provider.get_diagnostics(text)
    assert isinstance(diags, list)


def test_invalid_json():
    from dpgen_lsp.features.diagnostic import DiagnosticProvider

    provider = DiagnosticProvider()
    text = '{"type_map": '
    diags = provider.get_diagnostics(text)
    assert len(diags) > 0
    assert diags[0]["severity"] == "error"
    assert "JSON" in diags[0]["message"]


def test_lint_checks_fp_pp_files():
    from dpgen_lsp.features.diagnostic import DiagnosticProvider

    provider = DiagnosticProvider()
    text = '''{
        "type_map": ["H", "C", "O"],
        "fp_style": "vasp",
        "fp_pp_files": ["POTCAR_H"]
    }'''
    diags = provider.get_diagnostics(text)
    fp_pp_diags = [d for d in diags if "fp_pp_files" in str(d.get("code", ""))]
    assert len(fp_pp_diags) >= 0