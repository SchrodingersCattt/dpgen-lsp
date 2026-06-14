"""LSP diagnostic handler."""

from typing import Any

from lsprotocol.types import (
    Diagnostic,
    DiagnosticSeverity,
    Position,
    Range,
)

from ..features.diagnostic import DiagnosticProvider

_provider = DiagnosticProvider()


def diagnostic(ls: Any, params: Any) -> list[Diagnostic] | None:
    uri = params.text_document.uri
    text = _get_text(ls, uri)
    if not text:
        return None

    raw_diags = _provider.get_diagnostics(text, uri)
    result: list[Diagnostic] = []

    for raw in raw_diags:
        rng = raw.get("range", {})
        start = rng.get("start", {})
        end = rng.get("end", {})

        severity_map = {
            "error": DiagnosticSeverity.Error,
            "warning": DiagnosticSeverity.Warning,
            "information": DiagnosticSeverity.Information,
            "hint": DiagnosticSeverity.Hint,
        }

        result.append(Diagnostic(
            range=Range(
                start=Position(
                    line=start.get("line", 0),
                    character=start.get("character", 0),
                ),
                end=Position(
                    line=end.get("line", 0),
                    character=end.get("character", 0),
                ),
            ),
            severity=severity_map.get(raw.get("severity", "error"), DiagnosticSeverity.Error),
            code=raw.get("code", "diagnostic"),
            source=raw.get("source", "dpgen-lsp"),
            message=raw.get("message", ""),
        ))

    return result if result else None


def _get_text(ls: Any, uri: str) -> str:
    docs = getattr(ls, "documents", {})
    return docs.get(uri, "")