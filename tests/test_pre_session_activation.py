"""CI contract: pre-session activation scripts and manifest."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FIXTURE_MCPS = REPO / "tests" / "fixtures" / "mcp_minimal"


def _py(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    run_env = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=run_env,
        timeout=120,
        check=False,
    )


def test_check_agent_operations_ok():
    r = _py("scripts/check_agent_operations.py")
    assert r.returncode == 0, r.stderr or r.stdout


def test_validate_intake_loop_ok():
    r = _py("scripts/validate_intake_loop.py")
    assert r.returncode == 0, r.stderr or r.stdout


def test_pre_session_manifest_write_contract(tmp_path):
    out = tmp_path / "pre_session"
    r = _py(
        "scripts/pre_session_manifest.py",
        "--write",
        "--mcps-path",
        str(FIXTURE_MCPS),
        "--invoked-by",
        "pytest",
        env={
            "CHROMATIC_PRE_SESSION_DIR": str(out),
            "CHROMATIC_REPO": str(REPO),
        },
    )
    assert r.returncode == 0, r.stderr or r.stdout
    latest = out / "latest.json"
    assert latest.is_file()
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data["context_tier"] == "P0"
    assert data.get("pack_version")


def test_required_manifest_script_in_check_agent_operations():
    text = (REPO / "scripts" / "check_agent_operations.py").read_text(encoding="utf-8")
    assert "pre_session_manifest.py" in text
    assert "session_boot_automation.py" in text
    assert ".cursor/hooks.json" in text
    assert "07_LOGS_AND_AUDIT/pre_session/.gitkeep" in text
