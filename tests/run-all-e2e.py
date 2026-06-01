#!/usr/bin/env python3
"""Pre-push E2E gate runner — replaces the hung bats suite on Windows.

Runs the pytest-based harness tests with a clean subprocess and a
Python-native timeout, avoiding the GNU timeout process-group-kill
bug on Git Bash.

Usage:
    python tests/run-all-e2e.py [filter-pattern]

Exit 0 if all pass, 1 otherwise.
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEST_DIR = REPO / "tests"
PYTEST = "python -m pytest"
TIMEOUT_S = 120

# Test suites (each corresponds to one former .bats file)
SUITES = [
    (
        "model-router CORE + EDGE",
        [
            "test_complexity_and_routing.py",
        ],
    ),
    (
        "magnets pipeline (7 canonical + orchestrator)",
        [
            "test_canonical_magnets.py",
            "test_magnet_orchestrator.py",
            "test_magnet_plugins.py",
        ],
    ),
]


def run_suite(name: str, patterns: list[str]) -> int:
    print(f"\n--- {name} ---")
    args = [sys.executable, "-m", "pytest", "-v"]
    for p in patterns:
        args.append(str(TEST_DIR / p))
    try:
        result = subprocess.run(
            args,
            cwd=REPO,
            capture_output=False,
            text=True,
            timeout=TIMEOUT_S,
        )
        if result.returncode == 0:
            print(f"PASS: {name}")
        else:
            print(f"FAIL: {name} (exit {result.returncode})")
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT: {name} (>{TIMEOUT_S}s)")
        return 1


def main() -> int:
    print("pre-push: running harness E2E gates (pytest runner)…")

    # Gate 1: Validate skill routes (catch dead-end SKILL.md references)
    print("\n--- Skill Route Validation ---")
    skill_validator = REPO / "scripts" / "validate_skill_routes.py"
    if skill_validator.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(skill_validator), "--quiet"],
                cwd=REPO,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                print("PASS: All skill references resolve")
            else:
                print("FAIL: Dead-end skill references detected")
                print("  Run: python scripts/validate_skill_routes.py (for details)")
                return 1
        except subprocess.TimeoutExpired:
            print("TIMEOUT: Skill validation exceeded 10s")
            return 1
    else:
        print("SKIP: validate_skill_routes.py not found")

    failed = []
    for name, patterns in SUITES:
        rc = run_suite(name, patterns)
        if rc != 0:
            failed.append(name)

    if failed:
        print("\n" + "=" * 60)
        print("pre-push: E2E FAILED")
        for f in failed:
            print(f"  - {f}")
        print("=" * 60)
        return 1

    print("\n" + "=" * 60)
    print("pre-push: E2E PASSED — all suites green.")
    print("=" * 60)

    # Write last-pass marker
    marker = REPO / ".." / ".claude" / ".agents" / "test" / "last-pass.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    import json
    import datetime

    marker.write_text(
        json.dumps(
            {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "branch": "unknown",
                "commit": "unknown",
                "suites_pass": len(SUITES),
                "suites_fail": 0,
                "gate": "pre-push",
                "runner": "pytest",
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
