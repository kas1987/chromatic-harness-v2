"""Tests for roach-pi scope guards and submodule detection."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from adapters.roach_pi_guard import (  # noqa: E402
    detect_mode,
    load_manifest,
    submodule_healthy,
    validate_scope_paths,
)


def test_manifest_loads():
    manifest = load_manifest(REPO)
    assert manifest["runtime_id"] == "roach-pi"
    assert "tmdgusya/roach-pi" in manifest["upstream_url"]


def test_detect_mode_stub_when_submodule_empty():
    status = detect_mode(root=REPO)
    assert status["mode"] == "stub"
    assert not status["healthy"]


def test_validate_scope_rejects_traversal(tmp_path: Path):
    (tmp_path / "src").mkdir()
    bad = validate_scope_paths(["../etc/passwd"], tmp_path)
    assert not bad["valid"]
    good = validate_scope_paths(["src/"], tmp_path)
    assert good["valid"]
    assert good["normalized"] == ["src/"]


def test_submodule_healthy_with_markers(tmp_path: Path):
    root = tmp_path / "roach-pi"
    (root / "extensions" / "agentic-harness").mkdir(parents=True)
    (root / "extensions" / "agentic-harness" / "package.json").write_text("{}", encoding="utf-8")
    (root / "extensions" / "agentic-harness" / "index.ts").write_text("// stub", encoding="utf-8")
    assert submodule_healthy(root)
    status = detect_mode(roach_root=root, root=tmp_path)
    assert status["mode"] == "submodule"


def test_roach_pi_status_script():
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "roach_pi_status.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0
    assert "roach-pi" in proc.stdout
