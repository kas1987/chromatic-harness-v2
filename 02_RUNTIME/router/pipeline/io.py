"""I/O stage: read PreToolUse stdin, write hookSpecificOutput to stdout."""

from __future__ import annotations

import json
import sys
from typing import Any


def read_stdin() -> dict[str, Any]:
    data = sys.stdin.read()
    if not data:
        return {}
    try:
        result = json.loads(data)
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


def emit_advisory(advisory: str) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stdout.write(
        json.dumps(
            {"hookSpecificOutput": {"additionalContext": advisory}},
            ensure_ascii=False,
        )
    )


def emit_deny(advisory: str) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "permissionDecision": "deny",
                    "denyReason": f"Use cheaper tier instead. {advisory}",
                    "additionalContext": advisory,
                }
            },
            ensure_ascii=False,
        )
    )
