"""Tests for scripts/audit_mcp_context.py."""

import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "audit_mcp_context.py"
FIXTURE = REPO / "tests" / "fixtures" / "mcp_minimal"
HEAVY_FIXTURE = REPO / "tests" / "fixtures" / "mcp_heavy"


def _run_audit(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO,
        capture_output=True,
        text=True,
    )


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


def test_audit_strict_passes_on_minimal_fixture():
    result = _run_audit("--mcps-path", str(FIXTURE), "--strict")
    assert result.returncode == 0, result.stderr


def test_audit_strict_fails_on_heavy_server_fixture():
    result = _run_audit(
        "--mcps-path",
        str(HEAVY_FIXTURE),
        "--profile",
        "harness_dev",
        "--strict",
    )
    assert result.returncode == 1, result.stdout or result.stderr


def test_audit_strict_fails_when_over_token_budget(tmp_path):
    mcps = tmp_path / "mcps" / "plugin-test-server" / "tools"
    mcps.mkdir(parents=True)
    # ~50k chars → ~12.5k tokens, above default warn_total_tokens (12000)
    payload = {"name": "oversized_tool", "description": "x" * 50_000}
    (mcps / "oversized.json").write_text(json.dumps(payload), encoding="utf-8")

    result = _run_audit(
        "--mcps-path",
        str(tmp_path / "mcps"),
        "--profile",
        "harness_dev",
        "--strict",
        "--json",
    )
    assert result.returncode == 1, result.stderr
    data = json.loads(result.stdout)
    assert data["total_tokens_est"] > data["warn_threshold_tokens"]
