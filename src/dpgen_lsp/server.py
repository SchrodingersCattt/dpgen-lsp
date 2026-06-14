"""dpgen Language Server Protocol server wiring."""

from importlib import import_module
from typing import Any, Type, cast

from lsprotocol.types import (
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_FORMATTING,
    TEXT_DOCUMENT_RANGE_FORMATTING,
    Diagnostic as LspDiagnostic,
    DiagnosticSeverity,
    DidChangeTextDocumentParams,
    DidOpenTextDocumentParams,
    DocumentFormattingParams,
    DocumentRangeFormattingParams,
    Position,
    Range,
)

from . import __version__
from .constants import SERVER_NAME
from .features.code_actions import CodeActionProvider
from .features.diagnostic import DiagnosticProvider
from .features.formatting import FormattingProvider
from .features.lint import LintProvider
from .features.typecheck import TypecheckProvider
from .registry import register_handlers


def _load_language_server() -> Type[Any]:
    try:
        return cast(Type[Any], import_module("pygls.lsp.server").LanguageServer)
    except ImportError:
        return cast(Type[Any], import_module("pygls.server").LanguageServer)


LanguageServer = _load_language_server()


def _to_lsp_diagnostics(raw_diags: list[dict]) -> list[LspDiagnostic]:
    severity_map = {
        "error": DiagnosticSeverity.Error,
        "warning": DiagnosticSeverity.Warning,
        "information": DiagnosticSeverity.Information,
        "hint": DiagnosticSeverity.Hint,
    }
    result: list[LspDiagnostic] = []
    for raw in raw_diags:
        rng = raw.get("range", {})
        start = rng.get("start", {})
        end = rng.get("end", {})
        result.append(LspDiagnostic(
            range=Range(
                start=Position(line=start.get("line", 0), character=start.get("character", 0)),
                end=Position(line=end.get("line", 0), character=end.get("character", 0)),
            ),
            severity=severity_map.get(raw.get("severity", "error"), DiagnosticSeverity.Error),
            code=raw.get("code", "diagnostic"),
            source=raw.get("source", "dpgen-lsp"),
            message=raw.get("message", ""),
        ))
    return result


def create_server(name: str = SERVER_NAME, version: str = __version__) -> Any:
    lsp_server = LanguageServer(name, version)
    register_handlers(lsp_server)

    lsp_server.diagnostic_provider = DiagnosticProvider()  # type: ignore[attr-defined]

    lsp_server.lint_provider = LintProvider()  # type: ignore[attr-defined]

    lsp_server.typecheck_provider = TypecheckProvider()  # type: ignore[attr-defined]

    lsp_server.code_action_provider = CodeActionProvider()  # type: ignore[attr-defined]

    lsp_server.formatting_provider = FormattingProvider(lsp_server)  # type: ignore[attr-defined]

    lsp_server.documents = {}  # type: ignore[attr-defined]

    @_register(lsp_server, TEXT_DOCUMENT_DID_OPEN)
    def did_open(params: DidOpenTextDocumentParams) -> None:
        uri = params.text_document.uri
        text = params.text_document.text
        lsp_server.documents[uri] = text  # type: ignore[attr-defined]
        raw = lsp_server.diagnostic_provider.get_diagnostics(text, uri)  # type: ignore[attr-defined]
        raw.extend(lsp_server.lint_provider.lint(text))  # type: ignore[attr-defined]
        raw.extend(lsp_server.typecheck_provider.typecheck(text))  # type: ignore[attr-defined]
        lsp_server.publish_diagnostics(uri, _to_lsp_diagnostics(raw))

    @_register(lsp_server, TEXT_DOCUMENT_DID_CHANGE)
    def did_change(params: DidChangeTextDocumentParams) -> None:
        uri = params.text_document.uri
        if params.content_changes:
            text = params.content_changes[-1].text
            lsp_server.documents[uri] = text  # type: ignore[attr-defined]
            raw = lsp_server.diagnostic_provider.get_diagnostics(text, uri)  # type: ignore[attr-defined]
            raw.extend(lsp_server.lint_provider.lint(text))  # type: ignore[attr-defined]
            raw.extend(lsp_server.typecheck_provider.typecheck(text))  # type: ignore[attr-defined]
            lsp_server.publish_diagnostics(uri, _to_lsp_diagnostics(raw))

    @_register(lsp_server, TEXT_DOCUMENT_FORMATTING)
    def formatting(params: DocumentFormattingParams) -> list:
        uri = params.text_document.uri
        text = lsp_server.documents.get(uri, "")  # type: ignore[attr-defined]
        if not text:
            return []
        return cast(
            list,
            lsp_server.formatting_provider.format_document(text, params),  # type: ignore[attr-defined]
        )

    @_register(lsp_server, TEXT_DOCUMENT_RANGE_FORMATTING)
    def range_formatting(params: DocumentRangeFormattingParams) -> list:
        uri = params.text_document.uri
        text = lsp_server.documents.get(uri, "")  # type: ignore[attr-defined]
        if not text:
            return []
        return cast(
            list,
            lsp_server.formatting_provider.format_range(text, params),  # type: ignore[attr-defined]
        )

    return lsp_server


def _register(server: Any, feature_name: str) -> Any:
    return server.feature(feature_name)


server = create_server()


def main() -> None:
    server.start_io()


if __name__ == "__main__":
    main()