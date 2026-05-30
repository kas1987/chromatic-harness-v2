"""Tests for CHV2-003 IDE/CLI audit scripts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def test_audit_ide_parity_passes_in_repo():
    proc = subprocess.run(
        [PYTHON, str(REPO / "scripts" / "audit_ide_parity.py"), "--root", str(REPO)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )
    data = json.loads(proc.stdout.strip())
    assert data["audit"] == "ide_parity"
    assert proc.returncode == 0


def test_audit_instruction_drift_passes_in_repo():
    proc = subprocess.run(
        [PYTHON, str(REPO / "scripts" / "audit_instruction_drift.py"), "--root", str(REPO)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )
    data = json.loads(proc.stdout.strip())
    assert data["audit"] == "instruction_drift"
    assert proc.returncode == 0


def test_daily_harness_audit_report_writes_summary():
    proc = subprocess.run(
        [
            PYTHON,
            str(REPO / "scripts" / "daily_harness_audit.py"),
            "--root",
            str(REPO),
            "--report",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0
    summary = REPO / ".agents" / "audits" / "latest_audit_summary.md"
    assert summary.is_file()
    data = json.loads(proc.stdout.strip())
    assert data["audit"] == "daily_harness_audit"
    assert data["status"] in ("green", "yellow", "red")
