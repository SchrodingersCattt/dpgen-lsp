"""Agent-facing CLI for Diagnostic Engine v1 operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .agent_operations import operation_path, with_capabilities
from .rich_diagnostics import agent_check_payload
from .schema.official_rules import pipeline_steps, source_provenance
from . import templates as templates_lib

SOFTWARE = "dpgen"


def _capabilities_payload() -> dict[str, Any]:
    return {
        "schema": "OpenQCLspCapabilities",
        "version": 1,
        "software": SOFTWARE,
        "capabilities": [
            "diagnostics",
            "rich-diagnostics",
            "completion",
            "hover",
            "symbols",
            "fix-preview",
            "llm-wiki",
            "openqc-context",
        ],
        "pipeline": pipeline_steps(),
        "sourceProvenance": source_provenance(),
        "agentCli": {
            "operations": [
                "capabilities",
                "init",
                "check",
                "context",
                "complete",
                "hover",
                "symbols",
                "fix",
            ],
            "jsonFormat": True,
            "failOnBlocking": True,
        },
    }


def _file_type(path: Path) -> str:
    name = path.name.upper()
    if "PARAM" in name or "MACHINE" in name:
        return "json"
    if "." in path.name:
        return path.suffix.lstrip(".").lower()
    return name.lower()


def _collect_diagnostics(path: Path) -> list[Any]:
    from .features.diagnostic import DiagnosticProvider

    text = path.read_text(encoding="utf-8")
    base_dir = path.parent.resolve()
    return DiagnosticProvider().get_diagnostics(text, path.resolve().as_uri(), base_dir=base_dir)


def check_path(path: Path) -> dict[str, Any]:
    uri = path.resolve().as_uri()
    diagnostics = _collect_diagnostics(path)
    return agent_check_payload(
        software=SOFTWARE,
        uri=uri,
        operation="check",
        diagnostics=diagnostics,
        path=str(path),
        file_type=_file_type(path),
    )


def _operation_payload(
    path: Path,
    operation: str,
    line: int = 0,
    character: int = 0,
) -> dict[str, Any]:
    return operation_path(
        path,
        operation,
        software=SOFTWARE,
        file_type_func=_file_type,
        collect_diagnostics=_collect_diagnostics,
        line=line,
        character=character,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dpgen-lsp-tool")
    subparsers = parser.add_subparsers(dest="operation", required=True)
    capabilities = subparsers.add_parser("capabilities")
    capabilities.add_argument("--format", choices=["json"], default="json")

    # init subcommand
    init = subparsers.add_parser("init", help="Initialize dpgen input file from template")
    init.add_argument("path", type=Path, nargs="?", help="Output file path")
    init.add_argument("--template", type=str, help="Template key name or file path")
    init.add_argument("--kind", type=str, choices=["param", "machine"], help="Template kind filter")
    init.add_argument("--list", action="store_true", help="List available templates and exit")
    init.add_argument("--force", action="store_true", help="Overwrite existing file")
    init.add_argument("--stdout", action="store_true", help="Print template content to stdout")
    init.add_argument("--format", choices=["json"], default="json")

    for operation in ("check", "context", "complete", "hover", "symbols", "fix"):
        sub = subparsers.add_parser(operation)
        sub.add_argument("path", type=Path)
        sub.add_argument("--format", choices=["json"], default="json")
        sub.add_argument(
            "--line",
            type=int,
            default=0,
            help="0-based line for position-aware operations.",
        )
        sub.add_argument(
            "--character",
            type=int,
            default=0,
            help="0-based character for position-aware operations.",
        )
        if operation == "check":
            sub.add_argument("--fail-on-blocking", action="store_true")
    args = parser.parse_args(argv)

    if args.operation == "capabilities":
        print(json.dumps(_capabilities_payload(), indent=2, sort_keys=True))
        return 0

    # Handle init operation
    if args.operation == "init":
        import sys as _sys

        # List templates
        if args.list:
            templates = templates_lib.list_templates(args.kind)
            print(json.dumps({"templates": templates}, indent=2, ensure_ascii=False))
            return 0

        # Write template to stdout
        if args.stdout:
            if not args.template:
                print("Error: --template is required when using --stdout", file=_sys.stderr)
                return 1
            content = templates_lib.read_template(args.template, args.kind)
            if content is None:
                print(f"Error: template '{args.template}' not found", file=_sys.stderr)
                return 1
            print(content)
            return 0

        # Write template to file
        if not args.path:
            print("Error: path is required (or use --list or --stdout)", file=_sys.stderr)
            return 1

        if not args.template:
            print("Error: --template is required when writing to file", file=_sys.stderr)
            return 1

        result = templates_lib.write_template(args.template, args.path, args.kind, args.force)

        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("success") else 1

    # Handle other operations
    if args.operation == "check":
        payload = with_capabilities(check_path(args.path), "check")
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1 if getattr(args, "fail_on_blocking", False) and not payload["ok"] else 0
    payload = _operation_payload(args.path, args.operation, args.line, args.character)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
