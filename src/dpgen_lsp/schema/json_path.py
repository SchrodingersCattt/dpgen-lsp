"""JSON cursor position to path mapping."""

from __future__ import annotations

import json
from typing import Any


class JsonPathMapper:
    def __init__(self, text: str):
        self.text = text
        self._data: Any = None
        self._lines: list[str] = []
        self._line_to_key: dict[int, str] = {}
        self._parse()

    def _parse(self):
        try:
            self._data = json.loads(self.text)
        except json.JSONDecodeError:
            self._data = None
            return

        self._lines = self.text.splitlines()
        self._build_line_mapping()

    def _build_line_mapping(self):
        import re
        for line_no, raw_line in enumerate(self._lines):
            stripped = raw_line.strip()
            m = re.match(r'"([^"]+)"\s*:', stripped)
            if m:
                self._line_to_key[line_no] = m.group(1)

    def get_path_at(self, line: int, character: int) -> str:
        return self._line_to_key.get(line, "")

    def get_cursor_context(self, line: int, character: int) -> dict:
        current_line = ""
        if 0 <= line < len(self._lines):
            current_line = self._lines[line]

        before = self._lines[max(0, line - 3) : line]
        after = self._lines[line + 1 : line + 4]

        token = ""
        col = min(max(character, 0), len(current_line))
        word_start = col
        word_end = col
        for i in range(col, 0, -1):
            ch = current_line[i - 1]
            if ch.isalnum() or ch in ("_", "-", ".", "$"):
                word_start = i - 1
            else:
                break
        for i in range(col, len(current_line)):
            ch = current_line[i]
            if ch.isalnum() or ch in ("_", "-", ".", "$"):
                word_end = i + 1
            else:
                break
        token = current_line[word_start:word_end]

        return {
            "line_text": current_line,
            "token": token.strip(' "'),
            "word_range": {
                "start": {"line": line, "character": word_start},
                "end": {"line": line, "character": word_end},
            },
            "before": before,
            "after": after,
        }

    @staticmethod
    def extract_full_path(text: str, line: int, character: int) -> str:
        lines = text.splitlines()
        if line >= len(lines):
            return ""

        path_parts: list[str] = []

        for lno in range(line, -1, -1):
            raw = lines[lno]
            stripped = raw.strip()
            indent = len(raw) - len(raw.lstrip())

            if stripped.startswith("}"):
                continue

            key_match = _find_key_in_line(stripped)
            if key_match:
                if not path_parts or indent < _indent_of_line(lines, lno):
                    path_parts.insert(0, key_match)

            if stripped == "{" or stripped.startswith("{"):
                break

        return ".".join(path_parts)


def _find_key_in_line(line: str) -> str:
    import re
    stripped = line.strip()
    m = re.match(r'"([^"]+)"\s*:', stripped)
    if m:
        return m.group(1)
    return ""


def _indent_of_line(lines: list[str], line_no: int) -> int:
    if line_no >= len(lines):
        return 0
    return len(lines[line_no]) - len(lines[line_no].lstrip())


def is_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError:
        return False