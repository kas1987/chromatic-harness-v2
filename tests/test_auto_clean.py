"""Tests for scripts/auto_clean.py — Chromatic Harness V2.

Covers:
  - clean_pycache        (TestPycCleanup)
  - remove_empty_dirs    (TestEmptyDirCleanup)
  - clean_old_logs       (TestLogCleanup)
  - check_large_files    (TestLargeFileCheck)
  - report_stale_logs    (TestStaleLogReport)
  - dry-run vs --force   (TestDryRun)
  - summary output       (TestSummary)

All tests use tmp_path and real temp files; no stdlib mocking.
The script operates relative to HARNESS_ROOT (derived from __file__), so
every test that exercises a function directly monkey-patches the module-level
path constant so it points to our tmp tree — which is the correct approach
for an integration-style unit test without mocking filesystem calls.
"""

from __future__ import annotations

import importlib
import sys
import time
import types
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers to load auto_clean with a patched HARNESS_ROOT / LOGS_DIR
# ---------------------------------------------------------------------------

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "auto_clean.py"


def _load_module(harness_root: Path) -> types.ModuleType:
    """Import auto_clean as a fresh module each call, overriding paths."""
    spec = importlib.util.spec_from_file_location("auto_clean_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Override the module-level path constants so functions scan tmp_path
    mod.HARNESS_ROOT = harness_root
    mod.LOGS_DIR = harness_root / "07_LOGS_AND_AUDIT"
    return mod


# ---------------------------------------------------------------------------
# TestPycCleanup
# ---------------------------------------------------------------------------


class TestPycCleanup:
    """Tests for clean_pycache()."""

    def test_removes_pyc_files_in_force_mode(self, tmp_path: Path):
        pkg = tmp_path / "mypkg" / "__pycache__"
        pkg.mkdir(parents=True)
        pyc = pkg / "module.cpython-311.pyc"
        pyc.write_bytes(b"\x00" * 16)

        mod = _load_module(tmp_path)
        result = mod.clean_pycache(dry_run=False)

        assert not pyc.exists(), "pyc file should have been deleted in force mode"
        assert result["pyc_files"] == 1
        assert result["cache_dirs"] == 1

    def test_dry_run_does_not_remove_pyc_files(self, tmp_path: Path):
        pkg = tmp_path / "pkg" / "__pycache__"
        pkg.mkdir(parents=True)
        pyc = pkg / "mod.cpython-311.pyc"
        pyc.write_bytes(b"\x00" * 8)

        mod = _load_module(tmp_path)
        result = mod.clean_pycache(dry_run=True)

        assert pyc.exists(), "dry-run must NOT delete any files"
        assert result["pyc_files"] == 1
        assert result["cache_dirs"] == 1

    def test_no_pyc_files_returns_zero(self, tmp_path: Path):
        (tmp_path / "subdir").mkdir()

        mod = _load_module(tmp_path)
        result = mod.clean_pycache(dry_run=False)

        assert result["pyc_files"] == 0
        assert result["cache_dirs"] == 0

    def test_multiple_pyc_files_counted(self, tmp_path: Path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        for name in ("a.pyc", "b.pyc", "c.pyc"):
            (cache / name).write_bytes(b"\x00")

        mod = _load_module(tmp_path)
        result = mod.clean_pycache(dry_run=True)

        assert result["pyc_files"] == 3


# ---------------------------------------------------------------------------
# TestEmptyDirCleanup
# ---------------------------------------------------------------------------


class TestEmptyDirCleanup:
    """Tests for remove_empty_dirs()."""

    def test_removes_truly_empty_directory_in_force_mode(self, tmp_path: Path):
        empty = tmp_path / "empty_dir"
        empty.mkdir()

        mod = _load_module(tmp_path)
        result = mod.remove_empty_dirs(dry_run=False)

        assert not empty.exists(), "empty dir should be removed in force mode"
        assert result["empty_dirs_removed"] >= 1

    def test_dry_run_does_not_remove_empty_directory(self, tmp_path: Path):
        empty = tmp_path / "lonely_dir"
        empty.mkdir()

        mod = _load_module(tmp_path)
        result = mod.remove_empty_dirs(dry_run=True)

        assert empty.exists(), "dry-run must NOT delete directories"
        assert result["empty_dirs_removed"] >= 1

    def test_gitkeep_prevents_directory_deletion(self, tmp_path: Path):
        kept = tmp_path / "intentional_dir"
        kept.mkdir()
        (kept / ".gitkeep").write_text("")

        mod = _load_module(tmp_path)
        result = mod.remove_empty_dirs(dry_run=False)

        assert kept.exists(), ".gitkeep dirs must survive force mode"

    def test_non_empty_directory_is_not_removed(self, tmp_path: Path):
        non_empty = tmp_path / "has_content"
        non_empty.mkdir()
        (non_empty / "file.txt").write_text("data")

        mod = _load_module(tmp_path)
        result = mod.remove_empty_dirs(dry_run=False)

        assert non_empty.exists(), "non-empty dirs must not be touched"

    def test_no_empty_dirs_returns_zero(self, tmp_path: Path):
        (tmp_path / "populated").mkdir()
        (tmp_path / "populated" / "x.txt").write_text("x")

        mod = _load_module(tmp_path)
        result = mod.remove_empty_dirs(dry_run=False)

        assert result["empty_dirs_removed"] == 0


# ---------------------------------------------------------------------------
# TestDryRun
# ---------------------------------------------------------------------------


class TestDryRun:
    """Cross-cutting dry-run safety: nothing is deleted when dry_run=True."""

    def test_pyc_cleanup_dry_run_leaves_files_intact(self, tmp_path: Path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        pyc = cache / "keep.pyc"
        pyc.write_bytes(b"\xff")

        mod = _load_module(tmp_path)
        mod.clean_pycache(dry_run=True)

        assert pyc.exists()
        assert cache.exists()

    def test_empty_dir_cleanup_dry_run_leaves_dirs_intact(self, tmp_path: Path):
        dirs = [tmp_path / f"empty_{i}" for i in range(3)]
        for d in dirs:
            d.mkdir()

        mod = _load_module(tmp_path)
        mod.remove_empty_dirs(dry_run=True)

        for d in dirs:
            assert d.exists(), f"{d} should still exist after dry-run"

    def test_log_cleanup_dry_run_leaves_logs_intact(self, tmp_path: Path):
        logs_dir = tmp_path / "07_LOGS_AND_AUDIT"
        logs_dir.mkdir()
        old_log = logs_dir / "old.log"
        old_log.write_text("old content")
        # Force mtime to 10 days ago
        old_mtime = time.time() - (10 * 86_400)
        import os

        os.utime(old_log, (old_mtime, old_mtime))

        mod = _load_module(tmp_path)
        mod.clean_old_logs(dry_run=True)

        assert old_log.exists(), "dry-run must not delete log files"


# ---------------------------------------------------------------------------
# TestLogCleanup
# ---------------------------------------------------------------------------


class TestLogCleanup:
    """Tests for clean_old_logs() and report_stale_logs()."""

    def _make_old_log(self, path: Path, age_days: float) -> None:
        path.write_text("log content")
        mtime = time.time() - (age_days * 86_400)
        import os

        os.utime(path, (mtime, mtime))

    def test_removes_old_log_files_in_force_mode(self, tmp_path: Path):
        logs_dir = tmp_path / "07_LOGS_AND_AUDIT"
        logs_dir.mkdir()
        old_log = logs_dir / "old.log"
        self._make_old_log(old_log, age_days=10)

        mod = _load_module(tmp_path)
        result = mod.clean_old_logs(dry_run=False)

        assert not old_log.exists(), "old log should be deleted in force mode"
        assert result["removed"] == 1

    def test_recent_log_files_are_not_removed(self, tmp_path: Path):
        logs_dir = tmp_path / "07_LOGS_AND_AUDIT"
        logs_dir.mkdir()
        recent_log = logs_dir / "recent.log"
        self._make_old_log(recent_log, age_days=2)

        mod = _load_module(tmp_path)
        result = mod.clean_old_logs(dry_run=False)

        assert recent_log.exists(), "recent log must not be deleted"
        assert result["removed"] == 0

    def test_missing_logs_dir_returns_zero_without_crash(self, tmp_path: Path):
        # No 07_LOGS_AND_AUDIT directory created
        mod = _load_module(tmp_path)
        result = mod.clean_old_logs(dry_run=False)

        assert result["removed"] == 0

    def test_stale_log_report_counts_old_files(self, tmp_path: Path):
        logs_dir = tmp_path / "07_LOGS_AND_AUDIT"
        logs_dir.mkdir()
        for i in range(3):
            log = logs_dir / f"stale_{i}.txt"
            self._make_old_log(log, age_days=40)

        mod = _load_module(tmp_path)
        result = mod.report_stale_logs()

        assert result["stale_logs"] == 3

    def test_stale_log_report_ignores_fresh_files(self, tmp_path: Path):
        logs_dir = tmp_path / "07_LOGS_AND_AUDIT"
        logs_dir.mkdir()
        fresh = logs_dir / "fresh.log"
        fresh.write_text("new")  # mtime is now — well within 30 days

        mod = _load_module(tmp_path)
        result = mod.report_stale_logs()

        assert result["stale_logs"] == 0


# ---------------------------------------------------------------------------
# TestLargeFileCheck
# ---------------------------------------------------------------------------


class TestLargeFileCheck:
    """Tests for check_large_files()."""

    def test_small_files_not_reported(self, tmp_path: Path):
        (tmp_path / "small.bin").write_bytes(b"x" * 1024)  # 1 KB

        mod = _load_module(tmp_path)
        result = mod.check_large_files()

        assert result["large_files"] == 0

    def test_large_file_is_detected(self, tmp_path: Path):
        big = tmp_path / "big.bin"
        # Write just over 5 MB
        big.write_bytes(b"\x00" * (5 * 1024 * 1024 + 1))

        mod = _load_module(tmp_path)
        result = mod.check_large_files()

        assert result["large_files"] == 1
        names = [item[0] for item in result["items"]]
        assert "big.bin" in names

    def test_files_in_skip_dirs_are_ignored(self, tmp_path: Path):
        node_mod = tmp_path / "node_modules"
        node_mod.mkdir()
        big = node_mod / "huge.bin"
        big.write_bytes(b"\x00" * (6 * 1024 * 1024))

        mod = _load_module(tmp_path)
        result = mod.check_large_files()

        # node_modules is in _LARGE_FILE_SKIP_DIRS — must not appear
        assert result["large_files"] == 0


# ---------------------------------------------------------------------------
# TestSummary
# ---------------------------------------------------------------------------


class TestSummary:
    """Tests for print_summary() output."""

    def test_summary_dry_run_mode_label(self, capsys: pytest.CaptureFixture):
        mod = _load_module(Path("."))  # path irrelevant for summary
        results = {
            "pyc": {"pyc_files": 2, "cache_dirs": 1},
            "worktrees": {"status": "ok"},
            "empty_dirs": {"empty_dirs_removed": 0},
            "large_files": {"large_files": 0, "items": []},
            "stale_logs": {"stale_logs": 0},
            "old_logs": {"removed": 0},
            "tracked_pyc": {"tracked_pyc": 0, "files": []},
        }
        mod.print_summary(results, dry_run=True, errors=False)
        out = capsys.readouterr().out
        assert "DRY-RUN" in out

    def test_summary_force_mode_label(self, capsys: pytest.CaptureFixture):
        mod = _load_module(Path("."))
        results = {
            "pyc": {"pyc_files": 0, "cache_dirs": 0},
            "worktrees": {"status": "ok"},
            "empty_dirs": {"empty_dirs_removed": 1},
            "large_files": {"large_files": 0, "items": []},
            "stale_logs": {"stale_logs": 0},
            "old_logs": {"removed": 1},
            "tracked_pyc": {"tracked_pyc": 0, "files": []},
        }
        mod.print_summary(results, dry_run=False, errors=False)
        out = capsys.readouterr().out
        assert "APPLIED" in out

    def test_summary_errors_flag_triggers_error_message(self, capsys: pytest.CaptureFixture):
        mod = _load_module(Path("."))
        results = {
            "pyc": {"pyc_files": 0, "cache_dirs": 0},
            "worktrees": {"status": "error"},
            "empty_dirs": {"empty_dirs_removed": 0},
            "large_files": {"large_files": 0, "items": []},
            "stale_logs": {"stale_logs": 0},
            "old_logs": {"removed": 0},
            "tracked_pyc": {"tracked_pyc": 0, "files": []},
        }
        mod.print_summary(results, dry_run=False, errors=True)
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "error" in combined.lower()

    def test_summary_row_counts_match_inputs(self, capsys: pytest.CaptureFixture):
        mod = _load_module(Path("."))
        results = {
            "pyc": {"pyc_files": 3, "cache_dirs": 2},
            "worktrees": {"status": "ok"},
            "empty_dirs": {"empty_dirs_removed": 5},
            "large_files": {"large_files": 1, "items": [("big.bin", 6.1)]},
            "stale_logs": {"stale_logs": 4},
            "old_logs": {"removed": 2},
            "tracked_pyc": {"tracked_pyc": 0, "files": []},
        }
        mod.print_summary(results, dry_run=True, errors=False)
        out = capsys.readouterr().out
        # Spot-check: the numeric values surface in the output
        assert "3" in out  # pyc_files
        assert "5" in out  # empty_dirs
        assert "4" in out  # stale_logs
