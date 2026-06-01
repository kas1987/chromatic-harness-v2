#!/usr/bin/env python3
"""Validate basic structure of a Chromatic Harness JSONL event log."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = {"event_id", "timestamp", "event_type", "severity", "category", "message", "source", "status"}


def validate_line(line: str, line_no: int) -> list[str]:
    errors: list[str] = []
    try:
        event = json.loads(line)
    except json.JSONDecodeError as exc:
        return [f"Line {line_no}: invalid JSON: {exc}"]
    missing = REQUIRED - set(event)
    if missing:
        errors.append(f"Line {line_no}: missing required fields: {', '.join(sorted(missing))}")
    if not isinstance(event.get("source"), dict):
        errors.append(f"Line {line_no}: source must be object")
    elif "surface" not in event["source"]:
        errors.append(f"Line {line_no}: source.surface missing")
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
