#!/usr/bin/env python3
"""Fetch official DP-GEN docs and refresh provenance artifacts.

This script keeps the repo-local raw/provenance layer reproducible without
making the LSP runtime depend on network access. Runtime code reads the checked
in structured rule index under ``src/dpgen_lsp/schema/dpgen_rules.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RULE_INDEX = ROOT / "src" / "dpgen_lsp" / "schema" / "dpgen_rules.json"
RAW_ASSETS = ROOT / "raw" / "assets"


class TextExtractor(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag in {"p", "li", "h1", "h2", "h3", "pre", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "li", "h1", "h2", "h3", "pre", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line)


def load_sources() -> list[dict[str, str]]:
    rules = json.loads(RULE_INDEX.read_text(encoding="utf-8"))
    return [
        source
        for source in rules.get("sourceProvenance", [])
        if source.get("kind") == "official_docs" and source.get("url")
    ]


def fetch_source(source: dict[str, str], timeout: int) -> dict[str, str | int]:
    url = source["url"]
    req = Request(url, headers={"User-Agent": "dpgen-lsp-provenance/0.1"})
    with urlopen(req, timeout=timeout) as response:
        body = response.read()
        content_type = response.headers.get("content-type", "")
        final_url = response.geturl()
        status = response.status
    parser = TextExtractor()
    parser.feed(body.decode("utf-8", errors="replace"))
    text = parser.text()
    return {
        "id": source["id"],
        "label": source["label"],
        "url": url,
        "final_url": final_url,
        "status": status,
        "content_type": content_type,
        "sha256": hashlib.sha256(body).hexdigest(),
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text": text[:20000],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--offline", action="store_true", help="Only validate checked-in files.")
    args = parser.parse_args(argv)

    RAW_ASSETS.mkdir(parents=True, exist_ok=True)
    sources = load_sources()
    if args.offline:
        if not sources:
            raise SystemExit("no official sources in rule index")
        return 0

    fetched = [fetch_source(source, args.timeout) for source in sources]
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = {
        "schema": "DpgenOfficialDocsSnapshot/v1",
        "fetched_at": fetched_at,
        "pipeline": [
            "official-docs-fetch",
            "structured-schema-rules",
            "source-provenance",
            "tests",
            "lsp-runtime",
        ],
        "sources": fetched,
    }
    (RAW_ASSETS / "dpgen-official-docs.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    provenance = {
        "schema": "SourceProvenance/v1",
        "fetched_at": fetched_at,
        "rule_index": str(RULE_INDEX.relative_to(ROOT)),
        "sources": [
            {key: item[key] for key in ("id", "label", "url", "final_url", "status", "sha256")}
            for item in fetched
        ],
    }
    (RAW_ASSETS / "source-provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "sources": len(fetched), "raw_assets": str(RAW_ASSETS)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
