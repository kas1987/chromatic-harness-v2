#!/usr/bin/env python3
"""Run pre-swarm safety gates in one command.

Default behavior:
1) Force-refresh pre-session manifest
2) check_agent_operations
3) validate_governance_stack
4) context_trim_audit

Usage:
    python scripts/pre_swarm_gate.py
    python scripts/pre_swarm_gate.py --invoked-by preflight
    python scripts/pre_swarm_gate.py --no-boot
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

sys.path.insert(0, str(REPO / "scripts"))
from common_harness import run_safe  # noqa: E402


def _run_step(name: str, cmd: list[str]) -> tuple[bool, str]:
    proc = run_safe(cmd, cwd=REPO, timeout=900)

    if proc.returncode == 0:
        return True, ""

    tail = (proc.stderr or proc.stdout or "").strip()
    if len(tail) > 600:
        tail = tail[-600:]
    return False, tail


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pre-swarm context + governance gates")
    parser.add_argument(
        "--invoked-by",
        default="preflight",
        choices=["cursor", "claude", "scheduler", "preflight", "automation"],
        help="Invoked-by value for session_boot_automation",
    )
    parser.add_argument(
        "--no-boot",
        action="store_true",
        help="Skip session_boot_automation --force",
    )
    parser.add_argument(
        "extras",
        nargs="*",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    # Harden Windows operator flow: ignore accidental placeholder args like '.'.
    ignored = [x for x in args.extras if x.strip() in {".", "./", ".\\"}]
    unknown = [x for x in args.extras if x not in ignored]
    if ignored:
        print(f"INFO  ignored placeholder args: {' '.join(ignored)}")
    if unknown:
        print(f"INFO  ignored extra args: {' '.join(unknown)}")

    steps: list[tuple[str, list[str]]] = []
    if not args.no_boot:
        steps.append(
            (
                "session_boot_force",
                [
                    PYTHON,
                    str(REPO / "scripts" / "session_boot_automation.py"),
                    "--force",
                    "--invoked-by",
                    args.invoked_by,
                ],
            )
        )

    steps.extend(
        [
            (
                "check_agent_operations",
                [PYTHON, str(REPO / "scripts" / "check_agent_operations.py")],
            ),
            (
                "validate_governance_stack",
                [PYTHON, str(REPO / "scripts" / "validate_governance_stack.py")],
            ),
            (
                "context_trim_audit",
                [
                    PYTHON,
                    str(REPO / "scripts" / "context_trim_audit.py"),
                    "--root",
                    str(REPO),
                ],
            ),
        ]
    )

    failed: list[str] = []
    for name, cmd in steps:
        ok, tail = _run_step(name, cmd)
        if ok:
            print(f"PASS  {name}")
            continue
        failed.append(name)
        print(f"FAIL  {name}")
        if tail:
            print(tail)

    if failed:
        print(f"\nPre-swarm gate FAILED ({len(failed)}): {', '.join(failed)}", file=sys.stderr)
        return 1

    print("\nPre-swarm gate OK (all checks passed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
