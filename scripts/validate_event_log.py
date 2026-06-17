#!/usr/bin/env python3
"""Validate an ERROR_LOG.jsonl file against the harness event schema.

This module can be imported safely (no top-level side-effects) and also
run directly as a CLI script.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Keep scripts/ importable when run directly or from tests
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from common_harness import validate_record, repo_root  # noqa: E402


REQUIRED_FIELDS = {
    "event_id",
    "timestamp",
    "event_type",
    "severity",
    "category",
    "message",
    "source",
    "status",
}


def validate_line(line: str, lineno: int) -> list[str]:
    """Validate a single JSONL line.  Returns a (possibly empty) list of error strings."""
    try:
        rec = json.loads(line)
    except Exception as exc:
        return [f"Line {lineno}: invalid JSON: {exc}"]

    errors: list[str] = []

    missing = REQUIRED_FIELDS - set(rec.keys())
    if missing:
        missing_str = ", ".join(sorted(missing))
        errors.append(f"Line {lineno}: missing required fields: {missing_str}")

    src = rec.get("source")
    if not isinstance(src, dict):
        errors.append(f"Line {lineno}: source must be object")
    elif not src.get("surface"):
        errors.append(f"Line {lineno}: source.surface missing")

    # Delegate enum / type checks to common_harness (skip fields already reported)
    for err in validate_record(rec):
        if "missing required field" in err:
            continue
        if "source must be object" in err or "source.surface" in err:
            continue  # already handled above
        errors.append(f"Line {lineno}: {err}")

    return errors


def validate_file(path: Path) -> int:
    if not path.exists():
        print(f"Log file not found: {path}", file=sys.stderr)
        return 2

    failures = 0
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        errs = validate_line(line, lineno)
        for err in errs:
            print(err, file=sys.stderr)
        failures += len(errs)

    if failures:
        print(f"Validation failed: {failures} issue(s) in {path}")
        return 1
    print(f"Validation passed: {path}")
    return 0


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Validate ERROR_LOG.jsonl")
    ap.add_argument("--log", default="00_META/observability/ERROR_LOG.jsonl")
    ap.add_argument("--repo-root")
    args = ap.parse_args()
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    path = Path(args.log)
    path = path if path.is_absolute() else root / path
    return validate_file(path)


if __name__ == "__main__":
    raise SystemExit(main())
