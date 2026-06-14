"""LSP code action handler."""

from typing import Any

from lsprotocol.types import CodeAction, CodeActionParams


def code_action(ls: Any, params: CodeActionParams) -> list[CodeAction] | None:
    return None