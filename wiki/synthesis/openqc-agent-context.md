# OpenQC Agent Context

OpenQC should route DP-GEN JSON inputs to `dpgen-lsp` using the `dpgen-lsp-tool`
agent CLI for preflight diagnostics. The expected DiagnosticEnvelope/v1 output
includes `manual_ref`, `fix_hints`, `blocking`, and source-provenance-backed
diagnostic codes so agents can repair inputs before launching DP-GEN.
