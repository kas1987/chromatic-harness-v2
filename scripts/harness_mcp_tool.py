#!/usr/bin/env python3
"""Run Chromatic MCP handlers directly from CLI/VS Code tasks.

This bridges IDE tasks to the same tool handlers exposed by the stdio MCP server.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
RUNTIME = REPO / "02_RUNTIME"
SESSION_FILE = REPO / ".agents" / "handoffs" / "cursor_session_id.txt"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from chromatic_mcp.handlers import call_tool, list_tool_specs  # noqa: E402


def _clean_argv(argv: list[str]) -> list[str]:
    # Ignore accidental placeholder args (for example ".") from shell/task wrappers.
    return [arg for arg in argv if arg.strip() != "."]


def _tool_names() -> list[str]:
    return [spec["name"] for spec in list_tool_specs()]


def _parse_args_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("--args-json must decode to a JSON object")
    return parsed


def _coerce_value(raw: str) -> Any:
    text = raw.strip()
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered == "null":
        return None
    try:
        if text.startswith("0") and len(text) > 1 and text.isdigit():
            raise ValueError
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _parse_kv_pairs(items: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"invalid --arg '{item}', expected key=value")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid --arg '{item}', key cannot be empty")
        parsed[key] = _coerce_value(value)
    return parsed


def _detect_session_id() -> str:
    env_sid = os.environ.get("CHROMATIC_SESSION_ID", "").strip()
    if env_sid:
        return env_sid
    if SESSION_FILE.is_file():
        return SESSION_FILE.read_text(encoding="utf-8").strip()
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Invoke a Chromatic MCP tool by name")
    parser.add_argument("tool", choices=_tool_names(), help="Tool name to invoke")
    parser.add_argument(
        "--args-json",
        default="{}",
        help="JSON object with tool arguments",
    )
    parser.add_argument(
        "--arg",
        action="append",
        default=[],
        help="Additional argument as key=value (can be repeated)",
    )
    parser.add_argument(
        "--session-id",
        default="",
        help="Session id for concurrency lock ownership (auto-detected when omitted)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )

    safe_argv = _clean_argv(list(argv if argv is not None else sys.argv[1:]))
    args = parser.parse_args(safe_argv)

    try:
        payload = _parse_args_json(args.args_json)
        payload.update(_parse_kv_pairs(args.arg))
        session_id = args.session_id.strip() or _detect_session_id()
        if session_id and "session_id" not in payload:
            payload["session_id"] = session_id
    except (ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    os.chdir(REPO)
    result = call_tool(args.tool, payload)

    if args.pretty:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())