#!/usr/bin/env python3
"""Triage git pipeline failures into digest + dual-backlog intake.

Usage:
  python scripts/git_triage.py --from-log
  python scripts/git_triage.py --stderr-file err.txt --step push
  python scripts/git_triage.py --steps-json steps.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from activity.git_triage import classify_git_failure, triage_git_failure  # noqa: E402
from workflows.run_log import read_last_entry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Git failure triage")
    parser.add_argument("--from-log", action="store_true", help="Use last GIT SHIP / failed workflow log")
    parser.add_argument("--stderr-file", type=Path, help="Read stderr from file")
    parser.add_argument("--step", default="", help="Failed step name for classification")
    parser.add_argument("--steps-json", type=Path, help="JSON file with pipeline steps list")
    parser.add_argument("--bead-id", default="")
    parser.add_argument("--lane", choices=["agent", "human", "review"], default="human")
    args = parser.parse_args()

    steps: list[dict] = []
    stderr = ""
    bead_id = args.bead_id

    if args.steps_json and args.steps_json.is_file():
        steps = json.loads(args.steps_json.read_text(encoding="utf-8"))
    elif args.from_log:
        last = read_last_entry(REPO) or {}
        steps = last.get("steps", [])
        stderr = last.get("error", "")
        bead_id = bead_id or last.get("bead_id", "")
        if not steps and last.get("mode", "").upper().startswith("GIT"):
            stderr = stderr or json.dumps(last)[:2000]
    if args.stderr_file and args.stderr_file.is_file():
        stderr = args.stderr_file.read_text(encoding="utf-8")

    if args.step and not steps:
        steps = [{"status": "failed", "stderr": stderr, "cmd": args.step.split()}]

    if not steps and stderr:
        failure_class = classify_git_failure(stderr, args.step)
        print(json.dumps({"failure_class": failure_class, "classified_only": True}, indent=2))
        return 0

    if not steps:
        print(json.dumps({"error": "no steps or stderr provided"}, indent=2), file=sys.stderr)
        return 1

    result = triage_git_failure(REPO, steps=steps, bead_id=bead_id, lane=args.lane, stderr=stderr)
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
