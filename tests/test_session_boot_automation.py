"""Tests for hands-off session boot automation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BOOT_SCRIPT = REPO / "scripts" / "session_boot_automation.py"
FIXTURE_MCPS = REPO / "tests" / "fixtures" / "mcp_minimal"


def test_manifest_is_fresh_helper(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO / "scripts"))
    from session_boot_automation import manifest_is_fresh  # noqa: E402

    manifest_dir = tmp_path / "pre_session"
    manifest_dir.mkdir()
    latest = manifest_dir / "latest.json"
    now = datetime.now(timezone.utc).isoformat()
    latest.write_text(
        json.dumps({"generated_at": now, "context_tier": "P0"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CHROMATIC_PRE_SESSION_DIR", str(manifest_dir))
    assert manifest_is_fresh(6.0) is True
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    latest.write_text(
        json.dumps({"generated_at": old, "context_tier": "P0"}),
        encoding="utf-8",
    )
    assert manifest_is_fresh(1.0) is False


def test_boot_writes_manifest_with_force(tmp_path):
    out = tmp_path / "pre_session"
    env = {
        **os.environ,
        "CHROMATIC_PRE_SESSION_DIR": str(out),
        "CHROMATIC_REPO": str(REPO),
    }
    r = subprocess.run(
        [
            sys.executable,
            str(BOOT_SCRIPT),
            "--invoked-by",
            "automation",
            "--force",
            "--mcps-path",
            str(FIXTURE_MCPS),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert r.returncode == 0, r.stderr or r.stdout
    latest = out / "latest.json"
    assert latest.is_file()
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data["context_tier"] == "P0"


def test_boot_skips_when_fresh(tmp_path):
    out = tmp_path / "pre_session"
    out.mkdir(parents=True)
    now = datetime.now(timezone.utc).isoformat()
    (out / "latest.json").write_text(
        json.dumps(
            {
                "generated_at": now,
                "context_tier": "P0",
                "pack_version": "abc",
            }
        ),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "CHROMATIC_PRE_SESSION_DIR": str(out),
        "CHROMATIC_REPO": str(REPO),
    }
    r = subprocess.run(
        [
            sys.executable,
            str(BOOT_SCRIPT),
            "--invoked-by",
            "automation",
            "--mcps-path",
            str(FIXTURE_MCPS),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert r.returncode == 0, r.stderr or r.stdout
    assert "fresh" in (r.stderr or "").lower() or "fresh_skip" in (r.stdout or "")
