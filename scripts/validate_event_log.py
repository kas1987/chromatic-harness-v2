#!/usr/bin/env python3
"""Validate basic structure of a Chromatic Harness JSONL event log."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = {"event_id", "timestamp", "event_type", "severity", "category", "message", "source", "status"}

VALID_EVENT_TYPES = {
    "info",
    "error",
    "warning",
    "incident",
    "collision",
    "learning",
    "fix",
    "status_update",
    "command_result",
}
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
    "git_state",
    "command_failure",
    "manual_note",
    "validation_failure",
    "unknown",
}
VALID_STATUSES = {
    "open",
    "routed",
    "queued",
    "active",
    "resolved",
    "ignored",
    "failed",
    "incident_opened",
    "collision_opened",
}


def validate_line(line: str, line_no: int) -> list[str]:
    errors: list[str] = []
    try:
        event = json.loads(line)
    except json.JSONDecodeError as exc:
        return [f"Line {line_no}: invalid JSON: {exc}"]
    if not isinstance(event, dict):
        return [f"Line {line_no}: expected JSON object, got {type(event).__name__}"]
    missing = REQUIRED - set(event)
    if missing:
        errors.append(f"Line {line_no}: missing required fields: {', '.join(sorted(missing))}")
    if not isinstance(event.get("source"), dict):
        errors.append(f"Line {line_no}: source must be object")
    elif "surface" not in event["source"]:
        errors.append(f"Line {line_no}: source.surface missing")
    for field, valid in (
        ("event_type", VALID_EVENT_TYPES),
        ("severity", VALID_SEVERITIES),
        ("category", VALID_CATEGORIES),
        ("status", VALID_STATUSES),
    ):
        val = event.get(field)
        if val is not None and val not in valid:
            errors.append(f"Line {line_no}: invalid {field}: {val!r}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="00_META/observability/ERROR_LOG.jsonl")
    args = parser.parse_args()
    path = Path(args.log)
    if not path.exists():
        raise SystemExit(f"Log not found: {path}")
    all_errors: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle, start=1):
            if line.strip():
                all_errors.extend(validate_line(line, idx))
    if all_errors:
        print("Validation failed:")
        for error in all_errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"Validation passed: {path}")


if __name__ == "__main__":
    main()
