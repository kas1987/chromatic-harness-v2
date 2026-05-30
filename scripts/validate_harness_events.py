"""Validate 07_LOGS_AND_AUDIT/harness_events.jsonl against the harness event schema.

Usage:
    python scripts/validate_harness_events.py [--log PATH]

Exit codes:
    0 — all events valid (or log file does not exist)
    1 — one or more invalid events found
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

REQUIRED_FIELDS = {
    "event_id",
    "timestamp",
    "task_id",
    "agent",
    "model",
    "event_type",
    "confidence_score",
    "risk_level",
    "result",
}

VALID_EVENT_TYPES = frozenset(
    {
        "observe",
        "classify",
        "score",
        "dispatch",
        "execute",
        "validate",
        "record",
        "halt",
        "incident",
    }
)
VALID_RISK_LEVELS = frozenset({"low", "medium", "high", "critical", "unknown"})
VALID_RESULTS = frozenset({"passed", "failed", "blocked", "halted", "partial"})


def validate_event(event: dict, line_no: int) -> list[str]:
    """Return a list of validation error messages for one event dict."""
    errors: list[str] = []

    missing = REQUIRED_FIELDS - event.keys()
    if missing:
        errors.append(f"line {line_no}: missing required fields: {sorted(missing)}")

    et = event.get("event_type")
    if et is not None and et not in VALID_EVENT_TYPES:
        errors.append(f"line {line_no}: invalid event_type {et!r}")

    rl = event.get("risk_level")
    if rl is not None and rl not in VALID_RISK_LEVELS:
        errors.append(f"line {line_no}: invalid risk_level {rl!r}")

    res = event.get("result")
    if res is not None and res not in VALID_RESULTS:
        errors.append(f"line {line_no}: invalid result {res!r}")

    cs = event.get("confidence_score")
    if cs is not None:
        try:
            cs_f = float(cs)
            if not (0 <= cs_f <= 100):
                errors.append(
                    f"line {line_no}: confidence_score {cs} out of range [0, 100]"
                )
        except (TypeError, ValueError):
            errors.append(f"line {line_no}: confidence_score {cs!r} is not a number")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate harness_events.jsonl")
    parser.add_argument(
        "--log",
        default=str(REPO / "07_LOGS_AND_AUDIT" / "harness_events.jsonl"),
        help="Path to harness_events.jsonl (default: 07_LOGS_AND_AUDIT/harness_events.jsonl)",
    )
    args = parser.parse_args(argv)

    log_path = Path(args.log)

    if not log_path.exists():
        print("harness_events.jsonl not found — nothing to validate.")
        print("0 events, 0 valid, 0 invalid")
        return 0

    raw_lines = [
        ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    total = len(raw_lines)
    valid_count = 0
    invalid_count = 0
    all_errors: list[str] = []

    for i, line in enumerate(raw_lines, start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            all_errors.append(f"line {i}: JSON parse error — {exc}")
            invalid_count += 1
            continue

        errs = validate_event(event, i)
        if errs:
            all_errors.extend(errs)
            invalid_count += 1
        else:
            valid_count += 1

    if all_errors:
        for err in all_errors:
            print(f"  ERROR: {err}", file=sys.stderr)

    print(f"{total} events, {valid_count} valid, {invalid_count} invalid")

    return 0 if invalid_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
