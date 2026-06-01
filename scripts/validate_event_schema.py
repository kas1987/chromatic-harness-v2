#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from common_harness import validate_record, repo_root


def validate_file(path: Path) -> int:
    failures = 0
    if not path.exists():
        print(f"Missing log file: {path}", file=sys.stderr)
        return 2
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except Exception as e:
            print(f"{path}:{idx}: invalid json: {e}", file=sys.stderr)
            failures += 1
            continue
        if not isinstance(rec, dict):
            print(f"{path}:{idx}: event must be a JSON object, got {type(rec).__name__}", file=sys.stderr)
            failures += 1
            continue
        errs = validate_record(rec)
        for err in errs:
            print(f"{path}:{idx}: {err}", file=sys.stderr)
        failures += len(errs)
    if failures:
        print(f"FAILED: {failures} validation issue(s)", file=sys.stderr)
        return 1
    print(f"OK: {path}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="00_META/observability/ERROR_LOG.jsonl")
    ap.add_argument("--repo-root")
    args = ap.parse_args()
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    path = Path(args.log)
    path = path if path.is_absolute() else root / path
    return validate_file(path)


if __name__ == "__main__":
    raise SystemExit(main())
