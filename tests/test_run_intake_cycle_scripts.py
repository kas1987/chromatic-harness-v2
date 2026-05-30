"""Smoke tests for harness automation wrapper scripts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def test_automation_scripts_exist():
    names = [
        "run_intake_cycle.ps1",
        "run_intake_cycle.sh",
        "smoke_stack.ps1",
        "session_preflight.ps1",
        "install_automation_tasks.ps1",
    ]
    for name in names:
        assert (REPO / "scripts" / name).is_file(), name


def test_runbook_exists():
    assert (REPO / "docs" / "ops" / "HARNESS_AUTOMATION_RUNBOOK.md").is_file()


def test_validate_intake_loop_subprocess():
    proc = subprocess.run(
        [PYTHON, str(REPO / "scripts" / "validate_intake_loop.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_workflow_git_plan_json_subprocess():
    proc = subprocess.run(
        [
            PYTHON,
            str(REPO / "scripts" / "workflow_git.py"),
            "plan",
            "--confidence",
            "0",
            "--tests-passed",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "pipeline" in proc.stdout
