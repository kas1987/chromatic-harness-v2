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
    ("instruction_drift", [PYTHON, str(REPO / "scripts" / "audit_instruction_drift.py"), "--root", str(REPO)]),
    ("ide_parity", [PYTHON, str(REPO / "scripts" / "audit_ide_parity.py"), "--root", str(REPO)]),
    ("intake_loop", [PYTHON, str(REPO / "scripts" / "validate_intake_loop.py")]),
    ("context_trim", [PYTHON, str(REPO / "scripts" / "context_trim_audit.py")]),
    (
        "pytest_workflows",
        [PYTHON, "-m", "pytest", "tests/test_workflows.py", "-k", "self_heal", "-q"],
    ),
    ("pytest_guardrails", [PYTHON, "-m", "pytest", "tests/test_workflow_guardrails.py", "-q"]),
    ("karpathy_discipline", [PYTHON, str(REPO / "scripts" / "validate_karpathy_discipline.py")]),
]


def _context_trim_ok(stdout: str) -> bool:
    if '"risk_level": "red"' in stdout or "'risk_level': 'red'" in stdout:
        return False
    if '"risk_level": "orange"' in stdout or "'risk_level': 'orange'" in stdout:
        return False
    return True


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict-audit",
        action="store_true",
        help="Also require daily_harness_audit green under --strict",
    )
    args = parser.parse_args()

    failed: list[str] = []

    gates = list(GATES)
    if args.strict_audit:
        gates.append(
            (
                "daily_audit_strict",
                [
                    PYTHON,
                    str(REPO / "scripts" / "daily_harness_audit.py"),
                    "--root",
                    str(REPO),
                    "--strict",
                ],
            )
        )

    for name, cmd in gates:
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=600)
        ok = proc.returncode == 0
        if name == "context_trim" and ok:
            combined = proc.stdout + proc.stderr
            ok = _context_trim_ok(combined)
            if "Risk level: green" not in combined:
                audit_json = REPO / ".agents" / "context" / "context_trim_audit.json"
                if audit_json.is_file():
                    try:
                        import json

                        data = json.loads(audit_json.read_text(encoding="utf-8"))
                        ok = data.get("risk_level") == "green"
                    except (json.JSONDecodeError, OSError):
                        ok = False
                else:
                    ok = False
        if name == "daily_audit_strict" and ok:
            try:
                import json

                data = json.loads(proc.stdout)
                ok = data.get("status") == "green"
            except json.JSONDecodeError:
                ok = False
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
