"""Tests for scripts/auto_heal.py — per-healer unit tests using tmp_path.

Each healer is imported and exercised in isolation.  Module-level constants
(REPO, REQUIRED_INIT_DIRS, REQUIRED_GITIGNORE) are patched so the test
filesystem lives entirely inside tmp_path, keeping the real repository clean.
"""

from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_module() -> ModuleType:
    """Return a fresh import of auto_heal (re-import to reset module state)."""
    mod_name = "scripts.auto_heal"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    import scripts.auto_heal as ah  # noqa: PLC0415

    return ah


# ---------------------------------------------------------------------------
# 1. Missing __init__.py — detection and fix
# ---------------------------------------------------------------------------


class TestHealMissingInitFiles:
    def _make_ah(self, tmp_path: Path):
        ah = _load_module()
        pkg_dir = tmp_path / "02_RUNTIME"
        pkg_dir.mkdir()
        # Patch both REPO and REQUIRED_INIT_DIRS so relative_to() calls succeed
        ah.REPO = tmp_path
        ah.REQUIRED_INIT_DIRS = [pkg_dir]
        return ah, pkg_dir

    def test_creates_init_when_missing(self, tmp_path: Path) -> None:
        ah, pkg_dir = self._make_ah(tmp_path)
        result = ah.HealResult()

        ah.heal_missing_init_files(result, check_only=False)

        init_file = pkg_dir / "__init__.py"
        assert init_file.exists(), "__init__.py should have been created"
        assert "auto_heal" in init_file.read_text(encoding="utf-8")
        assert len(result.fixed) == 1
        assert result.unfixable == []
        assert result.skipped == []

    def test_check_only_does_not_create_init(self, tmp_path: Path) -> None:
        ah, pkg_dir = self._make_ah(tmp_path)
        result = ah.HealResult()

        ah.heal_missing_init_files(result, check_only=True)

        assert not (pkg_dir / "__init__.py").exists(), "check-only must not create files"
        assert len(result.skipped) == 1
        assert result.fixed == []

    def test_clean_when_init_already_present(self, tmp_path: Path) -> None:
        ah, pkg_dir = self._make_ah(tmp_path)
        (pkg_dir / "__init__.py").write_text("# existing\n", encoding="utf-8")
        result = ah.HealResult()

        ah.heal_missing_init_files(result, check_only=False)

        assert "missing-init" in result.clean
        assert result.fixed == []
        assert result.skipped == []

    def test_skips_nonexistent_directory(self, tmp_path: Path) -> None:
        ah = _load_module()
        ghost = tmp_path / "does_not_exist"
        # REPO must be tmp_path so relative_to() is consistent if a dir were found
        ah.REPO = tmp_path
        ah.REQUIRED_INIT_DIRS = [ghost]
        result = ah.HealResult()

        ah.heal_missing_init_files(result, check_only=False)

        # No directory → no issue found → clean
        assert "missing-init" in result.clean
        assert result.fixed == []
        assert result.unfixable == []


# ---------------------------------------------------------------------------
# 2. Stale git index.lock detection
# ---------------------------------------------------------------------------


class TestHealGitIndexLock:
    def _setup(self, tmp_path: Path):
        ah = _load_module()
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        ah.REPO = tmp_path
        return ah, git_dir

    def test_no_lock_file_is_clean(self, tmp_path: Path) -> None:
        ah, _ = self._setup(tmp_path)
        result = ah.HealResult()

        ah.heal_git_index_lock(result, check_only=False)

        assert "git-index-lock" in result.clean
        assert result.fixed == []

    def test_stale_lock_is_removed(self, tmp_path: Path) -> None:
        ah, git_dir = self._setup(tmp_path)
        lock = git_dir / "index.lock"
        lock.write_text("", encoding="utf-8")
        # Back-date mtime so the lock appears old (> 60 s)
        old_mtime = time.time() - 120
        import os

        os.utime(lock, (old_mtime, old_mtime))

        result = ah.HealResult()
        ah.heal_git_index_lock(result, check_only=False)

        assert not lock.exists(), "stale lock should be deleted"
        assert len(result.fixed) == 1
        assert result.unfixable == []

    def test_fresh_lock_is_left_alone(self, tmp_path: Path) -> None:
        ah, git_dir = self._setup(tmp_path)
        lock = git_dir / "index.lock"
        lock.write_text("", encoding="utf-8")
        # mtime is 'now' — healer should not touch it
        result = ah.HealResult()

        ah.heal_git_index_lock(result, check_only=False)

        assert lock.exists(), "fresh lock must not be removed"
        assert len(result.skipped) == 1
        assert result.fixed == []

    def test_check_only_stale_lock_not_removed(self, tmp_path: Path) -> None:
        ah, git_dir = self._setup(tmp_path)
        lock = git_dir / "index.lock"
        lock.write_text("", encoding="utf-8")
        import os

        old_mtime = time.time() - 200
        os.utime(lock, (old_mtime, old_mtime))

        result = ah.HealResult()
        ah.heal_git_index_lock(result, check_only=True)

        assert lock.exists(), "check-only must not delete the lock"
        assert len(result.skipped) == 1
        assert result.fixed == []


# ---------------------------------------------------------------------------
# 3. .gitignore entry checking
# ---------------------------------------------------------------------------


class TestHealGitignoreEntries:
    _REQUIRED = [
        ("*.pyc", "Compiled Python bytecode"),
        ("__pycache__/", "Python cache directories"),
    ]

    def _setup(self, tmp_path: Path):
        ah = _load_module()
        ah.REPO = tmp_path
        ah.REQUIRED_GITIGNORE = self._REQUIRED
        return ah

    def test_appends_missing_entries(self, tmp_path: Path) -> None:
        ah = self._setup(tmp_path)
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log\n", encoding="utf-8")

        result = ah.HealResult()
        ah.heal_gitignore_entries(result, check_only=False)

        content = gitignore.read_text(encoding="utf-8")
        assert "*.pyc" in content
        assert "__pycache__/" in content
        assert len(result.fixed) == 1
        assert result.unfixable == []

    def test_all_present_is_clean(self, tmp_path: Path) -> None:
        ah = self._setup(tmp_path)
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__/\n", encoding="utf-8")

        result = ah.HealResult()
        ah.heal_gitignore_entries(result, check_only=False)

        assert "gitignore" in result.clean
        assert result.fixed == []

    def test_creates_gitignore_when_absent(self, tmp_path: Path) -> None:
        ah = self._setup(tmp_path)
        result = ah.HealResult()

        ah.heal_gitignore_entries(result, check_only=False)

        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text(encoding="utf-8")
        assert "*.pyc" in content
        assert len(result.fixed) == 1

    def test_check_only_does_not_mutate(self, tmp_path: Path) -> None:
        ah = self._setup(tmp_path)
        gitignore = tmp_path / ".gitignore"
        original = "*.log\n"
        gitignore.write_text(original, encoding="utf-8")

        result = ah.HealResult()
        ah.heal_gitignore_entries(result, check_only=True)

        assert gitignore.read_text(encoding="utf-8") == original, "check-only must not modify .gitignore"
        assert len(result.skipped) == 1
        assert result.fixed == []

    def test_check_only_missing_gitignore_skips(self, tmp_path: Path) -> None:
        ah = self._setup(tmp_path)
        result = ah.HealResult()

        ah.heal_gitignore_entries(result, check_only=True)

        assert not (tmp_path / ".gitignore").exists()
        assert len(result.skipped) == 1
        assert result.fixed == []


# ---------------------------------------------------------------------------
# 4. Orphaned .pyc detection and removal
# ---------------------------------------------------------------------------


class TestHealOrphanedPyc:
    def _setup(self, tmp_path: Path):
        ah = _load_module()
        ah.REPO = tmp_path
        return ah

    def _make_pycache_pyc(self, parent: Path, module: str, *, orphan: bool) -> Path:
        """Create a __pycache__/module.cpython-311.pyc; optionally create .py source."""
        cache = parent / "__pycache__"
        cache.mkdir(exist_ok=True)
        pyc = cache / f"{module}.cpython-311.pyc"
        pyc.write_bytes(b"\x00" * 16)  # fake bytecode
        if not orphan:
            (parent / f"{module}.py").write_text(f"# {module}\n", encoding="utf-8")
        return pyc

    def test_orphaned_pyc_in_pycache_is_removed(self, tmp_path: Path) -> None:
        ah = self._setup(tmp_path)
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        orphan = self._make_pycache_pyc(pkg, "stale_module", orphan=True)
        assert orphan.exists()

        result = ah.HealResult()
        ah.heal_orphaned_pyc(result, check_only=False)

        assert not orphan.exists(), "orphaned .pyc must be deleted"
        assert len(result.fixed) == 1
        assert "1" in result.fixed[0]

    def test_pyc_with_live_source_is_kept(self, tmp_path: Path) -> None:
        ah = self._setup(tmp_path)
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        pyc = self._make_pycache_pyc(pkg, "live_module", orphan=False)

        result = ah.HealResult()
        ah.heal_orphaned_pyc(result, check_only=False)

        assert pyc.exists(), ".pyc with live .py must be preserved"
        assert "orphaned-pyc" in result.clean

    def test_check_only_does_not_delete(self, tmp_path: Path) -> None:
        ah = self._setup(tmp_path)
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        orphan = self._make_pycache_pyc(pkg, "stale", orphan=True)

        result = ah.HealResult()
        ah.heal_orphaned_pyc(result, check_only=True)

        assert orphan.exists(), "check-only must not delete .pyc files"
        assert len(result.skipped) == 1
        assert result.fixed == []

    def test_top_level_orphan_pyc_removed(self, tmp_path: Path) -> None:
        """Pre-Python-3.2 style .pyc adjacent to source directory, no .py companion."""
        ah = self._setup(tmp_path)
        orphan = tmp_path / "oldmodule.pyc"
        orphan.write_bytes(b"\x00" * 16)

        result = ah.HealResult()
        ah.heal_orphaned_pyc(result, check_only=False)

        assert not orphan.exists()
        assert len(result.fixed) == 1

    def test_no_pyc_files_is_clean(self, tmp_path: Path) -> None:
        ah = self._setup(tmp_path)
        result = ah.HealResult()

        ah.heal_orphaned_pyc(result, check_only=False)

        assert "orphaned-pyc" in result.clean
        assert result.fixed == []


# ---------------------------------------------------------------------------
# 5. --check-only flag end-to-end (via HealResult.ok and summary accumulation)
# ---------------------------------------------------------------------------


class TestCheckOnlyFlag:
    """Verify that check_only=True never mutates the filesystem and always
    populates result.skipped instead of result.fixed."""

    def test_missing_init_check_only_accumulates_skipped_not_fixed(self, tmp_path: Path) -> None:
        ah = _load_module()
        pkg = tmp_path / "runtime"
        pkg.mkdir()
        # REPO must align with pkg so relative_to() inside the healer succeeds
        ah.REPO = tmp_path
        ah.REQUIRED_INIT_DIRS = [pkg]

        result = ah.HealResult()
        ah.heal_missing_init_files(result, check_only=True)

        assert result.fixed == []
        assert len(result.skipped) == 1
        assert result.ok  # skipped does not affect ok; only unfixable does

    def test_heal_result_ok_false_only_when_unfixable(self, tmp_path: Path) -> None:
        ah = _load_module()
        result = ah.HealResult()
        assert result.ok is True

        result.unfixable.append("some issue")
        assert result.ok is False

        result.skipped.append("check-only skip")
        assert result.ok is False  # unfixable still present

    def test_all_healers_check_only_no_filesystem_writes(self, tmp_path: Path) -> None:
        """Run every targeted healer in check-only mode; confirm no new files appear."""
        ah = _load_module()

        # Set up a realistic but isolated tmp filesystem
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        # Stale index.lock
        lock = git_dir / "index.lock"
        lock.write_bytes(b"")
        import os

        os.utime(lock, (time.time() - 300, time.time() - 300))

        pkg = tmp_path / "02_RUNTIME"
        pkg.mkdir()

        ah.REPO = tmp_path
        ah.REQUIRED_INIT_DIRS = [pkg]
        ah.REQUIRED_GITIGNORE = [("*.pyc", "bytecode")]

        snapshot_before = {p for p in tmp_path.rglob("*")}

        result = ah.HealResult()
        ah.heal_missing_init_files(result, check_only=True)
        ah.heal_git_index_lock(result, check_only=True)
        ah.heal_gitignore_entries(result, check_only=True)
        ah.heal_orphaned_pyc(result, check_only=True)

        snapshot_after = {p for p in tmp_path.rglob("*")}
        new_paths = snapshot_after - snapshot_before

        assert new_paths == set(), f"check-only created unexpected files: {new_paths}"
        assert result.fixed == []

    def test_check_only_gitignore_missing_file_skipped_not_unfixable(self, tmp_path: Path) -> None:
        ah = _load_module()
        ah.REPO = tmp_path
        ah.REQUIRED_GITIGNORE = [("*.pyc", "bytecode")]
        result = ah.HealResult()

        ah.heal_gitignore_entries(result, check_only=True)

        # Missing .gitignore in check-only → skipped, not unfixable
        assert result.unfixable == []
        assert len(result.skipped) == 1


# ---------------------------------------------------------------------------
# 6. HealResult accumulator contract
# ---------------------------------------------------------------------------


class TestHealResult:
    def test_initial_state(self):
        ah = _load_module()
        r = ah.HealResult()
        assert r.fixed == []
        assert r.skipped == []
        assert r.unfixable == []
        assert r.clean == []
        assert r.ok is True

    def test_ok_becomes_false_on_unfixable(self):
        ah = _load_module()
        r = ah.HealResult()
        r.unfixable.append("broken thing")
        assert r.ok is False

    def test_ok_unaffected_by_skipped_or_fixed(self):
        ah = _load_module()
        r = ah.HealResult()
        r.skipped.append("skip1")
        r.fixed.append("fix1")
        r.clean.append("clean1")
        assert r.ok is True
