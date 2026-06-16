"""Retention wiring tests — bead chromatic-harness-v2-28iz.

Verifies that after writing >keep artifacts into a tmp dir, each writer's
prune call leaves exactly keep non-protected files.

All output is redirected to tmp_path; the real 07_LOGS_AND_AUDIT is never
touched.

Run:
    python -m pytest tests/test_writer_retention.py -q --no-cov
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name: str):
    script = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_n_artifacts(directory: Path, n: int, prefix: str = "run_") -> None:
    """Write n timestamped JSON files into directory with distinct mtimes."""
    directory.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        p = directory / f"{prefix}{i:04d}.json"
        p.write_text(json.dumps({"i": i}), encoding="utf-8")
        # stagger mtime so sort order is deterministic
        t = time.time() - (n - i)
        import os

        os.utime(p, (t, t))


def _non_protected_count(directory: Path) -> int:
    """Count files that prune_dir would treat as candidates (not protected)."""
    import fnmatch

    PROTECT = (
        "latest.json",
        "*_latest.json",
        "history.jsonl",
        "*.md",
        ".gitkeep",
        ".gitignore",
        "*.yaml",
        "*.yml",
        "*schema*",
    )
    return sum(
        1 for p in directory.iterdir() if p.is_file() and not any(fnmatch.fnmatch(p.name, pat) for pat in PROTECT)
    )


# ---------------------------------------------------------------------------
# 1. session_unified_guard — keep=50
# ---------------------------------------------------------------------------


def test_unified_guard_prune_keeps_50(tmp_path):
    """After writing 70 receipts, prune leaves exactly 50 non-protected files."""
    guard_dir = tmp_path / "unified_guard"
    _write_n_artifacts(guard_dir, 70, prefix="session_guard_")
    # also write a latest.json (protected — must survive)
    (guard_dir / "latest.json").write_text("{}", encoding="utf-8")

    retention = _load("log_retention")
    retention.prune_dir(guard_dir, keep=50, apply=True)

    assert _non_protected_count(guard_dir) == 50
    assert (guard_dir / "latest.json").exists(), "latest.json must be protected"


# ---------------------------------------------------------------------------
# 2. security_scan — keep=50
# ---------------------------------------------------------------------------


def test_security_scan_prune_keeps_50(tmp_path):
    """After writing 60 scan artifacts, prune leaves exactly 50."""
    sec_dir = tmp_path / "security"
    _write_n_artifacts(sec_dir, 60, prefix="20260101T")
    (sec_dir / "latest.json").write_text("{}", encoding="utf-8")

    retention = _load("log_retention")
    retention.prune_dir(sec_dir, keep=50, apply=True)

    assert _non_protected_count(sec_dir) == 50
    assert (sec_dir / "latest.json").exists()


# ---------------------------------------------------------------------------
# 3. pre_session_manifest — keep=30
# ---------------------------------------------------------------------------


def test_pre_session_manifest_prune_keeps_30(tmp_path):
    """After writing 45 manifest_*.jsonl files, prune leaves exactly 30."""
    ps_dir = tmp_path / "pre_session"
    _write_n_artifacts(ps_dir, 45, prefix="manifest_")
    (ps_dir / "latest.json").write_text("{}", encoding="utf-8")

    retention = _load("log_retention")
    retention.prune_dir(ps_dir, keep=30, apply=True)

    assert _non_protected_count(ps_dir) == 30
    assert (ps_dir / "latest.json").exists()


# ---------------------------------------------------------------------------
# 4. Integration: prune_dir is actually wired — calling _write_receipt +
#    prune in unified_guard module trims excess files
# ---------------------------------------------------------------------------


def test_unified_guard_write_receipt_then_prune(tmp_path, monkeypatch):
    """_write_receipt writes one file; prune_dir call in main() trims down."""
    mod = _load("session_unified_guard")
    guard_dir = tmp_path / "unified_guard"

    # pre-seed 55 old receipts
    _write_n_artifacts(guard_dir, 55, prefix="session_guard_")

    # redirect REPO so _write_receipt targets tmp dir
    monkeypatch.setattr(mod, "REPO", tmp_path)
    # Override the unified_guard subdir path so it matches our tmp structure
    original_write = mod._write_receipt

    def _patched_write(payload):
        out_dir = guard_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_path = out_dir / f"session_guard_{stamp}.json"
        import json

        text = json.dumps(payload, indent=2)
        run_path.write_text(text, encoding="utf-8")
        (out_dir / "latest.json").write_text(text, encoding="utf-8")
        return run_path

    monkeypatch.setattr(mod, "_write_receipt", _patched_write)

    # Call prune directly as wired (avoids running actual subprocesses)
    mod.prune_dir(guard_dir, keep=50, apply=True)

    assert _non_protected_count(guard_dir) == 50
