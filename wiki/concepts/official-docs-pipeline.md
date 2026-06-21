# Official Docs Pipeline

`dpgen-lsp` separates networked documentation refresh from LSP runtime behavior.
The refresh script fetches official DP-GEN HTML pages, stores normalized raw text
and hashes under `raw/assets`, and keeps source IDs aligned with the structured
rule index. The language server then uses the checked-in rule index for
completion, hover, diagnostics, fix hints, and `manual_ref` fields.
