#!/usr/bin/env python3
"""Confidence-gated git pipeline: commit → push → PR → merge.

Usage:
  python scripts/workflow_git.py plan --confidence 92 --verifier approve --tests-passed
  python scripts/workflow_git.py ship --confidence 92 --verifier approve --tests-passed --bead-id chromatic-harness-v2-abc
  python scripts/workflow_git.py ship --execute   # runs allowed steps (default is dry-run)
  python scripts/workflow_git.py ship --from-log  # read confidence from last GO VERIFY entry
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from workflows.git_automation import run_git_pipeline  # noqa: E402
from workflows.run_log import append_run_log, read_last_entry  # noqa: E402


def _run_pytest(repo: Path) -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=line"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    return proc.returncode == 0


def _context_from_log() -> dict:
    last = read_last_entry(REPO) or {}
    conf = last.get("confidence") or {}
    score = conf.get("confidence_score", 0)
    risk = conf.get("risk_level", "low")
    verifier = last.get("verifier") or {}
    verdict = verifier.get("decision") or last.get("verdict", "")
    approved = verdict in ("approve", "ok") or last.get("verifier_approved") is True
    return {
        "confidence": float(score),
        "risk_level": risk,
        "verifier_approved": approved,
        "bead_id": last.get("bead_id", ""),
    }


def cmd_plan(args: argparse.Namespace) -> int:
    ctx = _context_from_log() if args.from_log else {}
    confidence = args.confidence if args.confidence is not None else ctx.get("confidence", 0)
    risk = args.risk or ctx.get("risk_level", "low")
    verifier = args.verifier == "approve" or ctx.get("verifier_approved", False)
    tests = args.tests_passed or (args.run_tests and _run_pytest(REPO))

    result = run_git_pipeline(
        REPO,
        confidence=confidence,
        risk_level=risk,
        verifier_approved=verifier,
        tests_passed=tests,
        bead_id=args.bead_id or ctx.get("bead_id", ""),
        commit_message=args.message,
        dry_run=True,
        for_plan=True,
    )
    out = result.to_dict()
    append_run_log(REPO, {"mode": "GIT PLAN", **out})
    print(json.dumps(out, indent=2))
    return 0


def cmd_ship(args: argparse.Namespace) -> int:
    ctx = _context_from_log() if args.from_log else {}
    confidence = args.confidence if args.confidence is not None else ctx.get("confidence", 0)
    if confidence <= 0:
        print(json.dumps({"error": "confidence required (--confidence or --from-log)"}, indent=2))
        return 1

    risk = args.risk or ctx.get("risk_level", "low")
    verifier = args.verifier == "approve" or ctx.get("verifier_approved", False)
    if not verifier:
        print(json.dumps({"error": "verifier must approve (--verifier approve)"}, indent=2))
        return 1

    tests = args.tests_passed or (args.run_tests and _run_pytest(REPO))
    if not tests and not args.skip_tests:
        print(json.dumps({"error": "tests must pass (--tests-passed or --run-tests)"}, indent=2))
        return 1

    dry_run = not args.execute
    result = run_git_pipeline(
        REPO,
        confidence=confidence,
        risk_level=risk,
        verifier_approved=verifier,
        tests_passed=tests,
        bead_id=args.bead_id or ctx.get("bead_id", ""),
        commit_message=args.message,
        dry_run=dry_run,
    )
    out = result.to_dict()
    append_run_log(REPO, {"mode": "GIT SHIP", "execute": args.execute, **out})
    print(json.dumps(out, indent=2))

    failed = any(s.get("status") == "failed" for s in out.get("steps", []))
    if failed:
        return 1
    if not any(
        out["pipeline"].get(k)
        for k in ("commit", "push", "open_pr", "merge")
    ):
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Confidence-gated git pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--confidence", type=float, default=None)
    common.add_argument("--risk", choices=["low", "medium", "high", "critical"], default="low")
    common.add_argument("--verifier", choices=["approve", "reject"], default="reject")
    common.add_argument("--tests-passed", action="store_true")
    common.add_argument("--run-tests", action="store_true")
    common.add_argument("--bead-id", default="")
    common.add_argument("--message", default="")
    common.add_argument("--from-log", action="store_true")

    sub.add_parser("plan", parents=[common], help="Dry-run pipeline decision only")
    ship = sub.add_parser("ship", parents=[common], help="Run allowed git steps")
    ship.add_argument("--execute", action="store_true", help="Actually run git/gh (default dry-run)")
    ship.add_argument("--skip-tests", action="store_true", help="Skip tests gate (not recommended)")

    args = parser.parse_args()
    if args.command == "plan":
        return cmd_plan(args)
    return cmd_ship(args)


if __name__ == "__main__":
    raise SystemExit(main())
