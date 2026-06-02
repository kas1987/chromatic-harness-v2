#!/usr/bin/env python3
"""CI preflight quality gate — runs before GitHub handoff.

Stages (in order, fail-fast):
  1. ruff lint      — E/F/W rules per pyproject.toml
  2. import check   — key harness modules importable
  3. pytest         — run-all-e2e.py suites

Produces a machine-readable artifact at:
  07_LOGS_AND_AUDIT/preflight/latest.json
  07_LOGS_AND_AUDIT/preflight/<timestamp>.json

Exit 0 = all green. Exit 1 = gate failed. Exit 2 = usage error.

Usage:
    python scripts/ci_preflight.py              # full gate
    python scripts/ci_preflight.py --lint-only  # ruff only
    python scripts/ci_preflight.py --no-artifact  # skip artifact write
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from common_harness import run_safe  # noqa: E402

ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "preflight"

# Modules that must be importable for the harness to be healthy.
# sys.path is set to REPO/02_RUNTIME so these are bare dotted names.
IMPORT_CHECKS = [
    "router.router",
    "router.contracts",
    "router.complexity_classifier",
    "router.provider_selector",
]

RUNTIME_PATH = REPO / "02_RUNTIME"

TIMEOUT_LINT = 60
TIMEOUT_IMPORTS = 15
TIMEOUT_TESTS = 180


def _run(cmd: list[str], *, timeout: int, cwd: Path = REPO) -> tuple[int, str]:
    r = run_safe(cmd, cwd=cwd, timeout=timeout)
    if r.returncode == 124:
        return 1, f"TIMEOUT after {timeout}s"
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def stage_lint() -> dict:
    rc, out = _run(
        [sys.executable, "-m", "ruff", "check", "."],
        timeout=TIMEOUT_LINT,
    )
    return {
        "stage": "lint",
        "command": "ruff check .",
        "passed": rc == 0,
        "output": out.strip()[-2000:] if out.strip() else "All checks passed!",
    }


def stage_imports() -> dict:
    failures = []
    for mod in IMPORT_CHECKS:
        rc, out = _run(
            [sys.executable, "-c", f"import sys; sys.path.insert(0, {repr(str(RUNTIME_PATH))}); import {mod}"],
            timeout=TIMEOUT_IMPORTS,
        )
        if rc != 0:
            failures.append({"module": mod, "error": out.strip()[-500:]})
    return {
        "stage": "imports",
        "command": f"import check ({len(IMPORT_CHECKS)} modules)",
        "passed": len(failures) == 0,
        "failures": failures,
        "checked": IMPORT_CHECKS,
    }


def stage_tests() -> dict:
    rc, out = _run(
        [sys.executable, "tests/run-all-e2e.py"],
        timeout=TIMEOUT_TESTS,
    )
    return {
        "stage": "tests",
        "command": "python tests/run-all-e2e.py",
        "passed": rc == 0,
        "output": out.strip()[-3000:] if out.strip() else "",
    }


def write_artifact(result: dict, *, dry_run: bool = False) -> Path | None:
    if dry_run:
        return None
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = json.dumps(result, indent=2)
    stamped = ARTIFACT_DIR / f"{ts}.json"
    latest = ARTIFACT_DIR / "latest.json"
    stamped.write_text(payload, encoding="utf-8")
    latest.write_text(payload, encoding="utf-8")
    return latest


def main() -> int:
    parser = argparse.ArgumentParser(description="CI preflight gate")
    parser.add_argument("--lint-only", action="store_true")
    parser.add_argument("--no-artifact", action="store_true")
    args = parser.parse_args()

    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    stages: list[dict] = []
    overall_pass = True

    # Stage 1: lint
    print("preflight: [1/3] ruff lint...", flush=True)
    s = stage_lint()
    stages.append(s)
    if not s["passed"]:
        overall_pass = False
        print(f"  FAIL: {s['output'][:500]}")
    else:
        print("  PASS")

    if args.lint_only or not overall_pass:
        pass  # skip remaining stages only if early-exit on fail
    else:
        # Stage 2: imports
        print("preflight: [2/3] import checks...", flush=True)
        s = stage_imports()
        stages.append(s)
        if not s["passed"]:
            overall_pass = False
            for f in s["failures"]:
                print(f"  FAIL import {f['module']}: {f['error'][:200]}")
        else:
            print(f"  PASS ({len(s['checked'])} modules)")

        # Stage 3: tests
        print("preflight: [3/3] pytest E2E...", flush=True)
        s = stage_tests()
        stages.append(s)
        if not s["passed"]:
            overall_pass = False
            print(f"  FAIL: {s['output'][-500:]}")
        else:
            print("  PASS")

    result = {
        "timestamp": ts,
        "passed": overall_pass,
        "stages": stages,
        "stages_run": len(stages),
        "stages_passed": sum(1 for s in stages if s["passed"]),
        "stages_failed": sum(1 for s in stages if not s["passed"]),
    }

    artifact_path = write_artifact(result, dry_run=args.no_artifact)

    sep = "=" * 60
    status = "PASSED" if overall_pass else "FAILED"
    print(f"\n{sep}\npreflight: {status} — {result['stages_passed']}/{result['stages_run']} stages green")
    if artifact_path:
        print(f"artifact:  {artifact_path}")
    print(sep)

    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
