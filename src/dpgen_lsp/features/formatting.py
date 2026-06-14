"""JSON formatting provider.""der.\"\"\"

import json
from typing import Any


class FormattingProvider:

    def __init__(self, server: Any):
        self.server = server

    def format_document(self, text: str, params: Any = None) -> list[dict[str, Any]]:
        try:
            data = json.loads(text)
            formatted = json.dumps(data, indent=2, ensure_ascii=False)
            if formatted == text:
                return []
            return [
                {
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": len(text.splitlines()), "character": 0},
                    },
                    "newText": formatted,
                }
            ]
        except json.JSONDecodeError:
            return []

    def format_range(self, text: str, params: Any) -> list[dict[str, Any]]:
        return self.format_document(text, params)