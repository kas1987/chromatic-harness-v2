#!/usr/bin/env python3
"""Append a normalized Chromatic Harness event to ERROR_LOG.jsonl."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from redact_secrets import redact_text
except ImportError as _redact_err:
    raise SystemExit(
        f"redact_secrets unavailable ({_redact_err}): refusing to log without secret redaction"
    ) from _redact_err

DEFAULT_LOG = Path("00_META/observability/ERROR_LOG.jsonl")
VALID_EVENT_TYPES = {"info", "warning", "error", "incident", "collision", "learning"}
VALID_SEVERITIES = {"info", "low", "medium", "high", "critical"}
VALID_CATEGORIES = {
    "tool_failure",
    "file_collision",
    "test_failure",
    "dependency_error",
    "context_drift",
    "scope_breach",
    "secret_exposure",
    "loop_behavior",
    "model_misroute",
    "playbook_gap",
    "permission_error",
    "git_state_error",
    "environment_error",
    "artifact_error",
    "manual_note",
}
VALID_STATUSES = {"open", "triaged", "queued", "active", "resolved", "ignored", "escalated"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_event_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"evt_{stamp}_{uuid.uuid4().hex[:8]}"


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def require_valid(name: str, value: str, valid: set[str]) -> None:
    if value not in valid:
        raise SystemExit(f"Invalid {name}: {value}. Expected one of: {', '.join(sorted(valid))}")


def build_event(args: argparse.Namespace) -> dict[str, Any]:
    message, redacted_message = redact_text(args.message)
    raw_excerpt, redacted_excerpt = redact_text(args.raw_excerpt or "")
    command, redacted_command = redact_text(args.command or "")

    require_valid("event_type", args.event_type, VALID_EVENT_TYPES)
    require_valid("severity", args.severity, VALID_SEVERITIES)
    require_valid("category", args.category, VALID_CATEGORIES)
    require_valid("status", args.status, VALID_STATUSES)

    redacted = redacted_message or redacted_excerpt or redacted_command or args.redacted

    event = {
        "event_id": args.event_id or make_event_id(),
        "timestamp": args.timestamp or now_iso(),
        "repo": args.repo or Path.cwd().name,
        "workspace": args.workspace or "local",
        "event_type": args.event_type,
        "severity": args.severity,
        "category": args.category,
        "message": message,
        "source": {
            k: v
            for k, v in {
                "surface": args.source,
                "ide": args.ide,
                "agent": args.agent,
                "model": args.model,
                "session_id": args.session_id or os.environ.get("CHROMATIC_SESSION_ID", "manual"),
            }.items()
            if v is not None
        },
        "command": command,
        "files_touched": split_csv(args.files_touched),
        "error_signature": args.error_signature,
        "raw_excerpt": raw_excerpt,
        "redacted": bool(redacted),
        "suspected_cause": args.suspected_cause,
        "action_taken": args.action_taken,
        "status": args.status,
        "linked_fix": args.linked_fix,
        "linked_learning": args.linked_learning,
        "next_action": args.next_action,
        "metadata": {},
    }
    return event


def append_event(event: dict[str, Any], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log a Chromatic Harness event.")
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    parser.add_argument("--event-id")
    parser.add_argument("--timestamp")
    parser.add_argument("--repo")
    parser.add_argument("--workspace")
    parser.add_argument("--source", required=True, help="Surface, e.g. terminal, vscode, cursor, claude, codex, ci")
    parser.add_argument("--ide")
    parser.add_argument("--agent")
    parser.add_argument("--model")
    parser.add_argument("--session-id")
    parser.add_argument("--event-type", required=True, choices=sorted(VALID_EVENT_TYPES))
    parser.add_argument("--severity", required=True, choices=sorted(VALID_SEVERITIES))
    parser.add_argument("--category", required=True, choices=sorted(VALID_CATEGORIES))
    parser.add_argument("--message", required=True)
    parser.add_argument("--command")
    parser.add_argument("--files-touched", help="Comma-separated list")
    parser.add_argument("--error-signature")
    parser.add_argument("--raw-excerpt")
    parser.add_argument("--redacted", action="store_true")
    parser.add_argument("--suspected-cause")
    parser.add_argument("--action-taken")
    parser.add_argument("--status", default="open", choices=sorted(VALID_STATUSES))
    parser.add_argument("--linked-fix")
    parser.add_argument("--linked-learning")
    parser.add_argument("--next-action")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    event = build_event(args)
    append_event(event, Path(args.log))
    print(json.dumps({"logged": True, "event_id": event["event_id"], "log": args.log}, indent=2))


if __name__ == "__main__":
    main()
