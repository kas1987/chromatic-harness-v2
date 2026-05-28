#!/usr/bin/env python3
"""Claude hook policy gate.

Reads a Claude Code hook payload from stdin and emits a hook decision JSON.
Designed for PreToolUse-style permission checks.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent))

SAFE_BASH_PREFIXES = (
    "git status",
    "git diff",
    "git log",
    "python -m pytest",
    "pytest",
    "npm test",
    "npm run test",
    "npm run lint",
    "ruff check",
    "black .",
)

ASK_BASH_MARKERS = (
    "pip install",
    "npm install",
    "pnpm install",
    "yarn install",
    "docker",
    "git push",
    "git reset",
    "git clean",
)

DENY_BASH_MARKERS = (
    "sudo ",
    "rm -rf /",
    "rm -rf ~",
    "chmod -R 777",
    "cat ~/.ssh",
    "cat .env",
    "cat ~/.env",
)

ALLOWED_PATH_PREFIXES = (
    ".claude/",
    "hooks/",
    "config/",
    "docs/",
    "scripts/",
    "tests/",
    "knowledge/",
)

ASK_PATH_PREFIXES = (".github/",)

ASK_PATH_NAMES = {
    "Dockerfile",
    "docker-compose.yml",
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "requirements.txt",
}

DENY_PATH_NAMES = {
    ".env",
    "id_rsa",
    "id_ed25519",
}

DENY_PATH_SUFFIXES = (
    ".pem",
    ".key",
)


def emit(decision: str, reason: str, event: str = "PreToolUse") -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "permissionDecision": decision,
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    # Strip leading "./" prefix only — do NOT strip a bare leading dot,
    # as that would corrupt dotfile names like ".env" -> "env".
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def classify_path(path: str) -> tuple[str, str]:
    normalized = normalize_path(path)
    name = PurePosixPath(normalized).name

    if name in DENY_PATH_NAMES or normalized.endswith(DENY_PATH_SUFFIXES):
        return "deny", f"Blocked protected path: {path}"

    if normalized.startswith(".ssh/") or "/.ssh/" in normalized:
        return "deny", f"Blocked SSH material path: {path}"

    if normalized.startswith(ASK_PATH_PREFIXES) or name in ASK_PATH_NAMES:
        return "ask", f"Manual approval required for sensitive repo path: {path}"

    if normalized.startswith(ALLOWED_PATH_PREFIXES):
        return "allow", f"Allowed repo-governance path: {path}"

    return "ask", f"Unknown path requires review: {path}"


def classify_bash(command: str) -> tuple[str, str]:
    stripped = command.strip()

    if any(marker in stripped for marker in DENY_BASH_MARKERS):
        return "deny", f"Blocked dangerous command: {command}"

    if any(marker in stripped for marker in ASK_BASH_MARKERS):
        return "ask", f"Manual approval required for command: {command}"

    if any(stripped.startswith(prefix) for prefix in SAFE_BASH_PREFIXES):
        return "allow", f"Auto-approved safe command: {command}"

    return "ask", f"Unknown command requires review: {command}"


def classify_payload(payload: Dict[str, Any]) -> tuple[str, str]:
    tool_name = payload.get("tool_name") or payload.get("tool") or ""
    tool_input = payload.get("tool_input") or payload.get("input") or {}

    if tool_name == "Bash":
        return classify_bash(str(tool_input.get("command", "")))

    if tool_name in {"Edit", "Write", "MultiEdit"}:
        path = str(
            tool_input.get("file_path")
            or tool_input.get("path")
            or tool_input.get("filename")
            or ""
        )
        if not path:
            return "ask", f"No path found for {tool_name}; manual review required"
        return classify_path(path)

    return (
        "defer",
        f"No local policy for tool {tool_name}; deferring to Claude/default permissions",
    )


def _try_emit_audit_event(payload: Dict[str, Any], decision: str, reason: str) -> None:
    """Emit a permission_decision AgentOps JSONL event if audit_log is available."""
    try:
        from audit_log import append_event, build_event, DEFAULT_LOG_PATH
        import argparse

        tool_name = payload.get("tool_name") or payload.get("tool") or "unknown"
        tool_input = payload.get("tool_input") or payload.get("input") or {}
        action = str(
            tool_input.get("command") or tool_input.get("file_path") or tool_input.get("path") or ""
        )
        args = argparse.Namespace(
            event_type="permission_decision",
            event_id=None,
            timestamp=None,
            severity="info",
            source_repo=os.getenv("AGENTOPS_SOURCE_REPO", "kas1987/claude-config"),
            source_component="hooks.policy_gate",
            agent_id=os.getenv("AGENTOPS_AGENT_ID"),
            session_id=os.getenv("AGENTOPS_SESSION_ID"),
            task_id=os.getenv("AGENTOPS_TASK_ID"),
            run_id=os.getenv("AGENTOPS_RUN_ID"),
            parent_event_id=None,
            duration_ms=None,
        )
        event = build_event(
            args,
            {
                "tool": tool_name,
                "action": action,
                "decision": decision,
                "reason": reason,
            },
        )
        log_path = Path(os.getenv("AGENTOPS_LOG_PATH", str(DEFAULT_LOG_PATH)))
        append_event(event, log_path)
    except Exception:
        pass  # audit logging is best-effort; never break the hook


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        emit("ask", f"Invalid hook payload JSON: {exc}")
        return 0

    decision, reason = classify_payload(payload)
    emit(decision, reason)
    _try_emit_audit_event(payload, decision, reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
