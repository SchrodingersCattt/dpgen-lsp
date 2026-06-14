"""Code action provider for dpgen JSON input files."""

from __future__ import annotations

from typing import Any


class CodeActionProvider:

    def get_code_actions(self, text: str, line: int, character: int) -> list[dict[str, Any]]:
        return []

    def execute_command(self, command: str, arguments: list) -> Any:
        return None