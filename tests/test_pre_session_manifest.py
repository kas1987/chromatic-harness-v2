"""Tests for pre-session manifest writer."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MANIFEST_SCRIPT = REPO / "scripts" / "pre_session_manifest.py"
FIXTURE_MCPS = REPO / "tests" / "fixtures" / "mcp_minimal"

REQUIRED_KEYS = {
    "generated_at",
    "repo",
    "branch",
    "active_beads",
    "handoff_pointer",
    "mcp_profile",
    "context_tier",
    "loaded_docs",
    "blocked_bulk_sources",
    "routing_context",
    "mcp_audit",
    "pack_version",
}


@pytest.fixture
def manifest_out(tmp_path):
    out = tmp_path / "pre_session"
    out.mkdir()
    return out


def _run_manifest(out_dir: Path, *, write: bool = True) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "CHROMATIC_PRE_SESSION_DIR": str(out_dir),
        "CHROMATIC_REPO": str(REPO),
    }
    args = [
        sys.executable,
        str(MANIFEST_SCRIPT),
        "--mcps-path",
        str(FIXTURE_MCPS),
        "--invoked-by",
        "pytest",
    ]
    if write:
        args.append("--write")
    return subprocess.run(
        args,
        cwd=REPO,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )


def test_manifest_schema_and_write(manifest_out):
    r = _run_manifest(manifest_out)
    assert r.returncode == 0, r.stderr or r.stdout

    latest = manifest_out / "latest.json"
    assert latest.is_file()
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert REQUIRED_KEYS <= set(data.keys())
    assert data["context_tier"] == "P0"
    assert isinstance(data["active_beads"], list)
    assert data["mcp_profile"] == "harness_dev"
    assert "AGENT_OPERATIONS.md" in data["loaded_docs"]
    assert data["mcp_audit"]["estimated_tokens_if_enabled"] >= 0
    assert len(data["pack_version"]) == 16

    jsonl = list(manifest_out.glob("manifest_*.jsonl"))
    assert len(jsonl) >= 1


def test_build_manifest_import():
    sys.path.insert(0, str(REPO / "scripts"))
    from pre_session_manifest import build_manifest  # noqa: E402

    m = build_manifest(
        repo=REPO,
        mcps_path=FIXTURE_MCPS,
        profile_name="harness_dev",
        invoked_by="pytest",
    )
    assert m["context_tier"] == "P0"
    assert REQUIRED_KEYS <= set(m.keys())
