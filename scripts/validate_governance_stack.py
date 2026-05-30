#!/usr/bin/env python3
"""Run governance + workflow verification gates (single pass/fail report)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

GATES: list[tuple[str, list[str]]] = [
    ("agent_operations", [PYTHON, str(REPO / "scripts" / "check_agent_operations.py")]),
    ("instruction_governance", [PYTHON, str(REPO / "scripts" / "validate_instruction_governance.py")]),
    ("intake_loop", [PYTHON, str(REPO / "scripts" / "validate_intake_loop.py")]),
    ("context_trim", [PYTHON, str(REPO / "scripts" / "context_trim_audit.py")]),
    (
        "pytest_workflows",
        [PYTHON, "-m", "pytest", "tests/test_workflows.py", "-k", "self_heal", "-q"],
    ),
    ("pytest_guardrails", [PYTHON, "-m", "pytest", "tests/test_workflow_guardrails.py", "-q"]),
]


def _risk_not_red(stdout: str) -> bool:
    return '"risk": "red"' not in stdout and "'risk': 'red'" not in stdout


def main() -> int:
    failed: list[str] = []

    for name, cmd in GATES:
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=600)
        ok = proc.returncode == 0
        if name == "context_trim" and ok:
            ok = _risk_not_red(proc.stdout)
        if ok:
            print(f"PASS  {name}")
        else:
            failed.append(name)
            tail = (proc.stderr or proc.stdout)[-400:]
            print(f"FAIL  {name}: {tail}")

    if failed:
        print(f"\nGovernance stack FAILED ({len(failed)} gates)", file=sys.stderr)
        return 1

    print("\nGovernance stack OK (all gates passed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
