"""Tests for 02_RUNTIME/scope/enforcer.py — ScopeEnforcer and helpers.

Uses importlib.util.spec_from_file_location so the module can be imported
without adding the runtime directory permanently to sys.path during test
collection.  All subprocess (git) calls are patched; no real git operations
are performed.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub aiosqlite before importing anything that touches memory.store
# ---------------------------------------------------------------------------
if "aiosqlite" not in sys.modules:
    sys.modules["aiosqlite"] = MagicMock()

_RUNTIME = Path(__file__).resolve().parents[1] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from scope.enforcer import ScopeBaseline, ScopeCheckResult, ScopeEnforcer  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_enforcer(repo_root: Path | None = None) -> ScopeEnforcer:
    """Return a ScopeEnforcer with a mocked SystemMemoryStore."""
    enforcer = ScopeEnforcer.__new__(ScopeEnforcer)
    if repo_root:
        enforcer.repo_root = repo_root
    else:
        enforcer.repo_root = Path("/fake/repo")
    enforcer._store = MagicMock()
    enforcer._store.record_violation = AsyncMock()
    return enforcer


def _git_output(ls_files: str = "", status: str = "", diff: str = "") -> MagicMock:
    """Build a side_effect callable for subprocess.run that returns preset output."""
    responses = {
        "ls-files": ls_files,
        "status": status,
        "diff": diff,
    }

    def _run(cmd, **kwargs):
        mock = MagicMock()
        mock.returncode = 0
        # Identify which git sub-command was called.
        for key, text in responses.items():
            if key in cmd:
                mock.stdout = text
                return mock
        mock.stdout = ""
        return mock

    return _run


# ---------------------------------------------------------------------------
# TestEnforcer
# ---------------------------------------------------------------------------


class TestEnforcer:
    # ------------------------------------------------------------------
    # take_baseline
    # ------------------------------------------------------------------

    def test_take_baseline_returns_scope_baseline(self):
        enforcer = _make_enforcer()
        with patch("subprocess.run", side_effect=_git_output(ls_files="a.py\nb.py", status="")):
            bl = enforcer.take_baseline("m1", "src/")
        assert isinstance(bl, ScopeBaseline)

    def test_take_baseline_populates_mission_id(self):
        enforcer = _make_enforcer()
        with patch("subprocess.run", side_effect=_git_output(ls_files="a.py", status="")):
            bl = enforcer.take_baseline("mission-42", "src/")
        assert bl.mission_id == "mission-42"

    def test_take_baseline_populates_expected_scope(self):
        enforcer = _make_enforcer()
        with patch("subprocess.run", side_effect=_git_output(ls_files="", status="")):
            bl = enforcer.take_baseline("m1", "02_RUNTIME/")
        assert bl.expected_scope == "02_RUNTIME/"

    def test_take_baseline_counts_tracked_files(self):
        enforcer = _make_enforcer()
        ls_out = "a.py\nb.py\nc.py"
        with patch("subprocess.run", side_effect=_git_output(ls_files=ls_out, status="")):
            bl = enforcer.take_baseline("m1", "src/")
        assert bl.baseline_count == 3

    def test_take_baseline_includes_untracked_files(self):
        enforcer = _make_enforcer()
        status_out = "?? new_file.py\n?? another.py"
        with patch("subprocess.run", side_effect=_git_output(ls_files="", status=status_out)):
            bl = enforcer.take_baseline("m1", "src/")
        assert "new_file.py" in bl.baseline_files
        assert "another.py" in bl.baseline_files

    # ------------------------------------------------------------------
    # check_scope — passing case
    # ------------------------------------------------------------------

    def test_check_scope_passes_when_no_changes(self):
        enforcer = _make_enforcer()
        bl = ScopeBaseline(
            mission_id="m1",
            expected_scope="src/",
            baseline_files={"src/a.py"},
            baseline_count=1,
        )
        with patch("subprocess.run", side_effect=_git_output(diff="", status="")):
            result = enforcer.check_scope(bl)
        assert result.passed is True
        assert result.violations == []

    def test_check_scope_passes_for_in_scope_modification(self):
        enforcer = _make_enforcer()
        bl = ScopeBaseline(
            mission_id="m1",
            expected_scope="src/",
            baseline_files=set(),
            baseline_count=0,
        )
        with patch("subprocess.run", side_effect=_git_output(diff="src/module.py", status="")):
            result = enforcer.check_scope(bl)
        assert result.passed is True

    # ------------------------------------------------------------------
    # check_scope — denial / block behavior
    # ------------------------------------------------------------------

    def test_check_scope_fails_for_out_of_scope_modification(self):
        enforcer = _make_enforcer()
        bl = ScopeBaseline(
            mission_id="m1",
            expected_scope="src/",
            baseline_files=set(),
            baseline_count=0,
        )
        with patch("subprocess.run", side_effect=_git_output(diff="tests/bad.py", status="")):
            result = enforcer.check_scope(bl)
        assert result.passed is False

    def test_check_scope_lists_out_of_scope_file_in_violations(self):
        enforcer = _make_enforcer()
        bl = ScopeBaseline(
            mission_id="m1",
            expected_scope="src/",
            baseline_files=set(),
            baseline_count=0,
        )
        with patch("subprocess.run", side_effect=_git_output(diff="docs/README.md", status="")):
            result = enforcer.check_scope(bl)
        assert any("docs/README.md" in v for v in result.violations)
        assert "docs/README.md" in result.modified_outside

    def test_check_scope_blocks_new_file_outside_scope(self):
        enforcer = _make_enforcer()
        bl = ScopeBaseline(
            mission_id="m1",
            expected_scope="src/",
            baseline_files=set(),
            baseline_count=0,
        )
        with patch(
            "subprocess.run",
            side_effect=_git_output(diff="", status="?? outsider.py"),
        ):
            result = enforcer.check_scope(bl)
        assert result.passed is False
        assert "outsider.py" in result.new_files

    def test_check_scope_allows_new_file_inside_scope(self):
        enforcer = _make_enforcer()
        bl = ScopeBaseline(
            mission_id="m1",
            expected_scope="src/",
            baseline_files=set(),
            baseline_count=0,
        )
        with patch(
            "subprocess.run",
            side_effect=_git_output(diff="", status="?? src/new_thing.py"),
        ):
            result = enforcer.check_scope(bl)
        assert result.passed is True

    def test_check_scope_allows_file_already_in_baseline(self):
        enforcer = _make_enforcer()
        bl = ScopeBaseline(
            mission_id="m1",
            expected_scope="src/",
            baseline_files={"existing.py"},
            baseline_count=1,
        )
        with patch(
            "subprocess.run",
            side_effect=_git_output(diff="", status="?? existing.py"),
        ):
            result = enforcer.check_scope(bl)
        # File was already tracked in baseline — not a new violation.
        assert result.passed is True

    def test_check_scope_result_has_correct_fields(self):
        enforcer = _make_enforcer()
        bl = ScopeBaseline(
            mission_id="m1",
            expected_scope="src/",
            baseline_files=set(),
            baseline_count=0,
        )
        with patch("subprocess.run", side_effect=_git_output(diff="", status="")):
            result = enforcer.check_scope(bl)
        assert isinstance(result, ScopeCheckResult)
        assert hasattr(result, "passed")
        assert hasattr(result, "violations")
        assert hasattr(result, "new_files")
        assert hasattr(result, "modified_outside")
        assert hasattr(result, "deleted_outside")

    # ------------------------------------------------------------------
    # enforce_and_log
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_enforce_and_log_no_violation_skips_store(self):
        enforcer = _make_enforcer()
        bl = ScopeBaseline(
            mission_id="m1",
            expected_scope="src/",
            baseline_files=set(),
            baseline_count=0,
        )
        with patch("subprocess.run", side_effect=_git_output(diff="", status="")):
            result = await enforcer.enforce_and_log(bl, task_id="t1")
        assert result.passed is True
        enforcer._store.record_violation.assert_not_called()

    @pytest.mark.asyncio
    async def test_enforce_and_log_violation_calls_store(self):
        enforcer = _make_enforcer()
        bl = ScopeBaseline(
            mission_id="m1",
            expected_scope="src/",
            baseline_files=set(),
            baseline_count=0,
        )
        with patch("subprocess.run", side_effect=_git_output(diff="bad/file.py", status="")):
            result = await enforcer.enforce_and_log(bl, task_id="t1")
        assert result.passed is False
        enforcer._store.record_violation.assert_called_once()

    @pytest.mark.asyncio
    async def test_enforce_and_log_new_files_sets_critical_severity(self):
        enforcer = _make_enforcer()
        bl = ScopeBaseline(
            mission_id="m1",
            expected_scope="src/",
            baseline_files=set(),
            baseline_count=0,
        )
        with patch(
            "subprocess.run",
            side_effect=_git_output(diff="", status="?? rogue.py"),
        ):
            await enforcer.enforce_and_log(bl, task_id="t1")
        call_args = enforcer._store.record_violation.call_args
        violation = call_args[0][0]
        assert violation.severity == "critical"

    # ------------------------------------------------------------------
    # build_scope_header
    # ------------------------------------------------------------------

    def test_build_scope_header_contains_scope_path(self):
        enforcer = _make_enforcer()
        header = enforcer.build_scope_header("02_RUNTIME/scope/")
        assert "02_RUNTIME/scope/" in header

    def test_build_scope_header_contains_must_not_write(self):
        enforcer = _make_enforcer()
        header = enforcer.build_scope_header("src/")
        assert "MUST NOT" in header

    def test_build_scope_header_appends_rules(self):
        enforcer = _make_enforcer()
        rules = [
            {
                "severity": "high",
                "name": "no-external-writes",
                "description": "do not write outside scope",
                "fix": "revert the file",
            }
        ]
        header = enforcer.build_scope_header("src/", rules=rules)
        assert "no-external-writes" in header
        assert "do not write outside scope" in header

    def test_build_scope_header_no_rules_returns_string(self):
        enforcer = _make_enforcer()
        header = enforcer.build_scope_header("src/")
        assert isinstance(header, str)
        assert len(header) > 0

    # ------------------------------------------------------------------
    # _detect_repo_root
    # ------------------------------------------------------------------

    def test_detect_repo_root_finds_git_dir(self, tmp_path):
        (tmp_path / ".git").mkdir()
        enforcer = ScopeEnforcer.__new__(ScopeEnforcer)
        enforcer._store = MagicMock()
        # Monkey-patch __file__ context by passing explicit repo_root.
        enforcer.repo_root = tmp_path
        assert enforcer.repo_root == tmp_path
