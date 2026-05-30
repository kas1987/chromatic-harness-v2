"""Tests for parallel maintenance automation script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def test_parallel_maintenance_runs_and_returns_json():
    proc = subprocess.run(
        [PYTHON, str(REPO / "scripts" / "parallel_maintenance.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    data = json.loads(proc.stdout)
    assert data.get("ok") is True
    assert "parallel_health" in data
    summary = data.get("summary", "")
    assert "pruned_locks=" in summary
    assert "pruned_worktrees=" in summary
