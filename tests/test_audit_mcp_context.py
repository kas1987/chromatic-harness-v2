"""Tests for scripts/audit_mcp_context.py."""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "audit_mcp_context.py"
FIXTURE = REPO / "tests" / "fixtures" / "mcp_minimal"


def test_audit_fixture_ok():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--mcps-path",
            str(FIXTURE),
            "--profile",
            "harness_dev",
            "--json",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["total_tokens_est"] < 5000
    assert data["profile"] == "harness_dev"


def test_audit_strict_fails_on_heavy_fixture_if_present():
    # minimal fixture has no heavy servers — strict should pass
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--mcps-path",
            str(FIXTURE),
            "--strict",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
