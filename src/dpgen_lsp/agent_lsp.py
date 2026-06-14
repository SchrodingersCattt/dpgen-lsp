"""Small Python API wrapper around the Diagnostic Engine v1 CLI contract."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urlparse

from .agent_operations import operation_path, with_capabilities
from .tool import SOFTWARE, _collect_diagnostics, _file_type, check_path


class AgentLSP:
    """Agent-facing wrapper for non-editor LSP diagnostics."""

    def __init__(self, text: str | None = None, uri: str = "file:///input") -> None:
        self.text = text
        self.uri = uri

    @classmethod
    def from_text(cls, text: str, uri: str = "file:///input") -> "AgentLSP":
        return cls(text=text, uri=uri)

    @classmethod
    def from_path(cls, path: str | Path) -> "AgentLSP":
        return cls(text=None, uri=Path(path).resolve().as_uri())

    def check(self) -> dict[str, Any]:
        parsed = urlparse(self.uri)
        if self.text is None and parsed.scheme == "file":
            return with_capabilities(check_path(Path(parsed.path)), "check")
        suffix = Path(parsed.path).suffix if parsed.path else ""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / f"input{suffix}"
            path.write_text(self.text or "", encoding="utf-8")
            payload = check_path(path)
            payload["uri"] = self.uri
            return with_capabilities(payload, "check")

    def _operation(self, operation: str, line: int = 0, character: int = 0) -> dict[str, Any]:
        parsed = urlparse(self.uri)
        if self.text is None and parsed.scheme == "file":
            return operation_path(
                Path(parsed.path),
                operation,
                software=SOFTWARE,
                file_type_func=_file_type,
                collect_diagnostics=_collect_diagnostics,
                line=line,
                character=character,
            )
        suffix = Path(parsed.path).suffix if parsed.path else ""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / f"input{suffix}"
            path.write_text(self.text or "", encoding="utf-8")
            payload = operation_path(
                path,
                operation,
                software=SOFTWARE,
                file_type_func=_file_type,
                collect_diagnostics=_collect_diagnostics,
                line=line,
                character=character,
            )
            payload["uri"] = self.uri
            return payload

    def context(self, line: int = 0, character: int = 0) -> dict[str, Any]:
        return self._operation("context", line, character)

    def complete(self, line: int = 0, character: int = 0) -> dict[str, Any]:
        return self._operation("complete", line, character)

    def hover(self, line: int = 0, character: int = 0) -> dict[str, Any]:
        return self._operation("hover", line, character)

    def symbols(self) -> dict[str, Any]:
        return self._operation("symbols")