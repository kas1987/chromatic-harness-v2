"""Tests for scripts/check_agent_operations.py."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "check_agent_operations.py"


def test_check_agent_operations_passes_on_repo():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
