"""Tests for the official-docs -> rules -> runtime pipeline."""

from __future__ import annotations

import json
from pathlib import Path


def test_static_schema_fallback_has_official_fields():
    from dpgen_lsp.schema.loader import load_schema_tree
    from dpgen_lsp.schema.official_rules import source_provenance

    schema = load_schema_tree("run")

    assert schema.root is not None
    assert schema.find_node("type_map") is not None
    assert schema.find_node("sys_configs") is not None
    assert any("example-of-param" in source["url"] for source in source_provenance())


def test_capabilities_include_pipeline_and_provenance(capsys):
    from dpgen_lsp import tool

    assert tool.main(["capabilities"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["pipeline"] == [
        "official-docs-fetch",
        "structured-schema-rules",
        "source-provenance",
        "tests",
        "lsp-runtime",
    ]
    assert any(
        source["id"] == "dpgen-run-example-machine" for source in payload["sourceProvenance"]
    )


def test_docs_backed_diagnostics_include_manual_ref(tmp_path: Path):
    from dpgen_lsp.features.diagnostic import DiagnosticProvider

    text = json.dumps(
        {
            "type_map": ["H", "C"],
            "mass_map": [1],
            "init_data_sys": ["missing/deepmd"],
            "sys_configs": [["missing/scale*/POSCAR"]],
            "numb_models": 1,
            "model_devi_f_trust_lo": 0.2,
            "model_devi_f_trust_hi": 0.1,
            "fp_style": "vasp",
            "fp_pp_files": ["POTCAR_H"],
        },
        indent=2,
    )

    diagnostics = DiagnosticProvider().get_diagnostics(text, base_dir=tmp_path)
    by_code = {item["code"]: item for item in diagnostics}

    assert "mass_map.lint" in by_code
    assert "path.sys_configs" in by_code
    assert by_code["mass_map.lint"]["manual_ref"].startswith("https://docs.deepmodeling.com/")
    assert by_code["path.sys_configs"]["manual_ref"].startswith("https://docs.deepmodeling.com/")
    assert by_code["numb_models.lint"]["blocking"] is False


def test_machine_sections_are_validated_without_dpdispatcher():
    from dpgen_lsp.features.diagnostic import DiagnosticProvider

    text = json.dumps({"api_version": "1.0", "train": {}})

    diagnostics = DiagnosticProvider().get_diagnostics(text)
    by_code = {item["code"]: item for item in diagnostics}

    assert "machine.section.type" in by_code
    assert "machine.section.missing" in by_code
    assert by_code["machine.section.type"]["manual_ref"].endswith("example-of-machine.html")


def test_raw_official_docs_snapshot_matches_rule_sources():
    from dpgen_lsp.schema.official_rules import source_provenance

    root = Path(__file__).resolve().parents[1]
    raw = json.loads((root / "raw" / "assets" / "dpgen-official-docs.json").read_text())
    raw_ids = {source["id"] for source in raw["sources"]}
    official_ids = {
        source["id"] for source in source_provenance() if source["kind"] == "official_docs"
    }

    assert official_ids <= raw_ids
    assert raw["pipeline"][-1] == "lsp-runtime"
