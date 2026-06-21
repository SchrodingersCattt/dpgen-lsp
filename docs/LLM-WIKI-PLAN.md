# DP-GEN LSP Official-Docs Pipeline

This repo keeps a repeatable pipeline for agent-facing DP-GEN input validation:

1. Fetch official DP-GEN docs with `python3 scripts/update_official_pipeline.py`.
2. Normalize the raw docs into `raw/assets/dpgen-official-docs.json`.
3. Maintain structured field/rule/provenance data in `src/dpgen_lsp/schema/dpgen_rules.json`.
4. Verify provenance and runtime behavior with `PYTHONPATH=src python3 -m pytest`.
5. Expose the results through `dpgen-lsp-tool check/context/complete/hover/symbols/fix`.

The runtime is offline-safe: it reads the checked-in structured rule index and does not fetch network content during diagnostics.
