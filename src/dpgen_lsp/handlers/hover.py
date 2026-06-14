"""LSP hover handler."""

from typing import Any

from lsprotocol.types import Hover, HoverParams, MarkupContent, MarkupKind

from ..features.hover import hover_contents


def hover(ls: Any, params: HoverParams) -> Hover | None:
    uri = params.text_document.uri
    text = _get_text(ls, uri)
    if not text:
        return None

    line = params.position.line
    character = params.position.character

    contents = hover_contents(text, line, character)
    if contents is None:
        return None

    return Hover(
        contents=MarkupContent(kind=MarkupKind.Markdown, value=contents),
    )


def _get_text(ls: Any, uri: str) -> str:
    docs = getattr(ls, "documents", {})
    return docs.get(uri, "")