"""Tests for hands-off session boot automation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


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


def test_boot_fails_strict_on_heavy_mcps(tmp_path):
    out = tmp_path / "pre_session"
    env = {
        **os.environ,
        "CHROMATIC_PRE_SESSION_DIR": str(out),
        "CHROMATIC_REPO": str(REPO),
    }
    heavy = REPO / "tests" / "fixtures" / "mcp_heavy"
    r = subprocess.run(
        [
            sys.executable,
            str(BOOT_SCRIPT),
            "--invoked-by",
            "automation",
            "--force",
            "--mcps-path",
            str(heavy),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert r.returncode == 1, r.stderr or r.stdout
    assert "audit_mcp_context failed" in (r.stderr or "")


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


def test_manifest_is_fresh_requires_boot_context(tmp_path, monkeypatch):
    """manifest_is_fresh returns False when BOOT_CONTEXT.md is absent."""
    sys.path.insert(0, str(REPO / "scripts"))
    import importlib
    import session_boot_automation  # noqa: E402

    importlib.reload(session_boot_automation)

    manifest_dir = tmp_path / "pre_session"
    manifest_dir.mkdir()
    # repo root without BOOT_CONTEXT.md
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()

    now = datetime.now(timezone.utc).isoformat()
    (manifest_dir / "latest.json").write_text(
        json.dumps({"generated_at": now, "context_tier": "P0"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CHROMATIC_PRE_SESSION_DIR", str(manifest_dir))
    monkeypatch.setenv("CHROMATIC_REPO", str(fake_repo))
    assert session_boot_automation.manifest_is_fresh(6.0) is False

    # Now create BOOT_CONTEXT.md — should become fresh
    (fake_repo / ".agents" / "context").mkdir(parents=True)
    (fake_repo / ".agents" / "context" / "BOOT_CONTEXT.md").write_text("# ok")
    assert session_boot_automation.manifest_is_fresh(6.0) is True


def test_manifest_is_fresh_detects_newer_mcp_descriptor(tmp_path, monkeypatch):
    """manifest_is_fresh returns False when an MCP .json is newer than the manifest."""
    sys.path.insert(0, str(REPO / "scripts"))
    import importlib
    import session_boot_automation  # noqa: E402

    importlib.reload(session_boot_automation)

    # Setup: repo with BOOT_CONTEXT.md
    fake_repo = tmp_path / "repo"
    ctx_dir = fake_repo / ".agents" / "context"
    ctx_dir.mkdir(parents=True)
    (ctx_dir / "BOOT_CONTEXT.md").write_text("# ok")

    # MCP dir with one descriptor
    mcp_dir = tmp_path / "mcps"
    mcp_dir.mkdir()
    mcp_file = mcp_dir / "server.json"
    mcp_file.write_text(json.dumps({"name": "test"}))

    manifest_dir = tmp_path / "pre_session"
    manifest_dir.mkdir()
    manifest = manifest_dir / "latest.json"

    # Write manifest FIRST, then touch mcp_file to make it newer
    now = datetime.now(timezone.utc).isoformat()
    manifest.write_text(
        json.dumps({"generated_at": now, "mcp_audit": {"mcps_path": str(mcp_dir)}}),
        encoding="utf-8",
    )
    import time

    time.sleep(0.05)
    mcp_file.touch()  # mcp descriptor now newer than manifest

    monkeypatch.setenv("CHROMATIC_PRE_SESSION_DIR", str(manifest_dir))
    monkeypatch.setenv("CHROMATIC_REPO", str(fake_repo))
    assert session_boot_automation.manifest_is_fresh(6.0) is False


def test_boot_summary_includes_manifest_age(tmp_path):
    """run_boot output JSON includes manifest_age_hours."""
    out = tmp_path / "pre_session"
    out.mkdir(parents=True)
    # Create BOOT_CONTEXT.md in the actual repo so freshness passes
    now = datetime.now(timezone.utc).isoformat()
    (out / "latest.json").write_text(
        json.dumps({"generated_at": now, "context_tier": "P0", "pack_version": "x"}),
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
    summary = json.loads(r.stdout)
    assert "manifest_age_hours" in summary
    assert isinstance(summary["manifest_age_hours"], float)
