"""Feature registry for pygls handlers."""

from typing import Any, Callable, List, Tuple

from .handlers.code_action import code_action
from .handlers.completion import completion
from .handlers.definition import definition
from .handlers.diagnostic import diagnostic
from .handlers.document_symbol import document_symbol
from .handlers.hover import hover
from .handlers.references import references
from .handlers.rename import prepare_rename, rename

Handler = Callable[[Any], Any]


def default_handlers() -> List[Tuple[str, Handler]]:
    return [
        ("textDocument/completion", completion),
        ("textDocument/hover", hover),
        ("textDocument/definition", definition),
        ("textDocument/references", references),
        ("textDocument/documentSymbol", document_symbol),
        ("textDocument/diagnostic", diagnostic),
        ("textDocument/codeAction", code_action),
        ("textDocument/prepareRename", prepare_rename),
        ("textDocument/rename", rename),
    ]


def register_handlers(server: Any) -> None:
    for feature_name, handler in default_handlers():
        server.feature(feature_name)(handler)