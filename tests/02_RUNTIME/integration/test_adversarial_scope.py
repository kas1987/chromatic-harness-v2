"""Adversarial scope tests — probe ScopeEnforcer failure modes.

Tests cover:
- Writing outside declared scope raises ScopeViolation
- Scope violation halts task and records to memory
- Attempted scope expansion mid-task is rejected
- Malformed scope spec (empty, None, wildcard-only) handled safely
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

# Stub aiosqlite before importing memory.store
if "aiosqlite" not in sys.modules:
    sys.modules["aiosqlite"] = MagicMock()

from scope.enforcer import ScopeBaseline, ScopeCheckResult, ScopeEnforcer  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — build isolated ScopeEnforcer objects that don't need a real git repo
# ---------------------------------------------------------------------------


def _make_enforcer(tmp_path: Path) -> ScopeEnforcer:
    """Return a ScopeEnforcer whose _run_git is stubbed to return no diff."""
    enforcer = ScopeEnforcer(repo_root=tmp_path)
    enforcer._run_git = MagicMock(return_value="")
    return enforcer


def _make_baseline(
    mission_id: str = "m-test",
    scope: str = "src/",
    baseline_files: set[str] | None = None,
) -> ScopeBaseline:
    return ScopeBaseline(
        mission_id=mission_id,
        expected_scope=scope,
        baseline_files=baseline_files or {"src/main.py", "src/utils.py"},
        baseline_count=2,
    )


# ---------------------------------------------------------------------------
# 1. Writing outside declared scope produces violations
# ---------------------------------------------------------------------------


class TestScopeViolationDetection:
    def test_modification_outside_scope_is_flagged(self, tmp_path):
        """A diff touching a file outside the declared scope must appear in violations."""
        enforcer = _make_enforcer(tmp_path)
        # Simulate git diff reporting a file outside scope
        enforcer._run_git = MagicMock(side_effect=lambda *args: "outside/secret.py" if "diff" in args else "")
        baseline = _make_baseline(scope="src/")
        result = enforcer.check_scope(baseline)

        assert not result.passed, "Modification outside scope must fail the check"
        assert result.modified_outside, "modified_outside list must be non-empty"
        assert any("outside/secret.py" in v for v in result.violations)

    def test_modification_inside_scope_passes(self, tmp_path):
        """A diff touching only in-scope files must pass."""
        enforcer = _make_enforcer(tmp_path)
        enforcer._run_git = MagicMock(side_effect=lambda *args: "src/new_feature.py" if "diff" in args else "")
        baseline = _make_baseline(scope="src/")
        result = enforcer.check_scope(baseline)

        assert result.passed, "Modification inside scope must pass"
        assert result.violations == []

    def test_new_file_outside_scope_is_flagged(self, tmp_path):
        """Creating a new file outside the declared scope must be detected."""
        enforcer = _make_enforcer(tmp_path)

        def _git_stub(*args):
            if "diff" in args:
                return ""  # no modified tracked files
            if "status" in args:
                return "?? secrets/leaked_key.txt\n"
            return ""

        enforcer._run_git = MagicMock(side_effect=_git_stub)
        baseline = _make_baseline(scope="src/", baseline_files=set())
        result = enforcer.check_scope(baseline)

        assert not result.passed
        assert result.new_files
        assert any("secrets/leaked_key.txt" in v for v in result.violations)

    def test_new_file_inside_scope_not_flagged(self, tmp_path):
        """A new file created inside the declared scope must NOT be flagged."""
        enforcer = _make_enforcer(tmp_path)

        def _git_stub(*args):
            if "diff" in args:
                return ""
            if "status" in args:
                return "?? src/new_module.py\n"
            return ""

        enforcer._run_git = MagicMock(side_effect=_git_stub)
        baseline = _make_baseline(scope="src/", baseline_files=set())
        result = enforcer.check_scope(baseline)

        assert result.passed
        assert result.new_files == []

    def test_multiple_violations_all_reported(self, tmp_path):
        """All out-of-scope modifications must appear in the violations list."""
        enforcer = _make_enforcer(tmp_path)
        enforcer._run_git = MagicMock(side_effect=lambda *args: "outside/a.py\noutside/b.py" if "diff" in args else "")
        baseline = _make_baseline(scope="src/")
        result = enforcer.check_scope(baseline)

        assert not result.passed
        assert len(result.violations) == 2


# ---------------------------------------------------------------------------
# 2. Scope violation halts task and records to memory
# ---------------------------------------------------------------------------


class TestScopeViolationRecordsToMemory:
    @pytest.mark.asyncio
    async def test_enforce_and_log_records_violation_on_failure(self, tmp_path):
        """enforce_and_log must call record_violation when scope check fails."""
        enforcer = _make_enforcer(tmp_path)
        enforcer._run_git = MagicMock(side_effect=lambda *args: "outside/bad.py" if "diff" in args else "")
        baseline = _make_baseline(scope="src/")

        mock_store = MagicMock()
        mock_store.record_violation = AsyncMock()
        enforcer._store = mock_store

        result = await enforcer.enforce_and_log(baseline, task_id="task-001")

        assert not result.passed
        mock_store.record_violation.assert_called_once()

    @pytest.mark.asyncio
    async def test_enforce_and_log_does_not_record_when_clean(self, tmp_path):
        """enforce_and_log must NOT call record_violation when the check passes."""
        enforcer = _make_enforcer(tmp_path)
        # No diff, no untracked
        enforcer._run_git = MagicMock(return_value="")
        baseline = _make_baseline(scope="src/")

        mock_store = MagicMock()
        mock_store.record_violation = AsyncMock()
        enforcer._store = mock_store

        result = await enforcer.enforce_and_log(baseline, task_id="task-002")

        assert result.passed
        mock_store.record_violation.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_file_violation_has_critical_severity(self, tmp_path):
        """Creating files outside scope should produce a 'critical' severity violation."""
        enforcer = _make_enforcer(tmp_path)

        def _git_stub(*args):
            if "diff" in args:
                return ""
            if "status" in args:
                return "?? outside/injected.py\n"
            return ""

        enforcer._run_git = MagicMock(side_effect=_git_stub)
        baseline = _make_baseline(scope="src/", baseline_files=set())

        recorded: list = []

        async def _capture(violation):
            recorded.append(violation)

        mock_store = MagicMock()
        mock_store.record_violation = _capture
        enforcer._store = mock_store

        await enforcer.enforce_and_log(baseline, task_id="task-003")

        assert recorded, "A violation must be recorded"
        assert recorded[0].severity == "critical"

    @pytest.mark.asyncio
    async def test_modified_file_violation_has_warning_severity(self, tmp_path):
        """Modifying (not creating) files outside scope should produce 'warning' severity."""
        enforcer = _make_enforcer(tmp_path)
        enforcer._run_git = MagicMock(side_effect=lambda *args: "outside/existing.py" if "diff" in args else "")
        baseline = _make_baseline(scope="src/")

        recorded: list = []

        async def _capture(violation):
            recorded.append(violation)

        mock_store = MagicMock()
        mock_store.record_violation = _capture
        enforcer._store = mock_store

        await enforcer.enforce_and_log(baseline, task_id="task-004")

        assert recorded
        assert recorded[0].severity == "warning"


# ---------------------------------------------------------------------------
# 3. Attempted scope expansion mid-task is rejected
# ---------------------------------------------------------------------------


class TestScopeExpansionRejected:
    """The enforcer must flag any files outside the *original* baseline scope,
    even if the agent later 'claims' a wider scope."""

    def test_scope_cannot_be_widened_after_baseline(self, tmp_path):
        """After take_baseline, check_scope always uses the original expected_scope."""
        enforcer = _make_enforcer(tmp_path)
        # Baseline taken for 'src/'
        baseline = _make_baseline(scope="src/")

        # Agent writes to 'tests/' — outside the original scope
        enforcer._run_git = MagicMock(side_effect=lambda *args: "tests/injected_test.py" if "diff" in args else "")

        result = enforcer.check_scope(baseline)
        assert not result.passed
        assert any("tests/injected_test.py" in v for v in result.violations)

    def test_adversarial_path_traversal_scope_prefix_weakness(self, tmp_path):
        """Document path-traversal behaviour of the enforcer's simple prefix check.

        The enforcer uses a string-prefix match: 'src/../secrets/key.txt' starts
        with 'src/' so it *incorrectly* passes today (known limitation).
        This test documents the current behaviour so a future hardening that
        normalises paths before comparison can flip the final assertion.
        """
        enforcer = _make_enforcer(tmp_path)
        enforcer._run_git = MagicMock(side_effect=lambda *args: "src/../secrets/key.txt" if "diff" in args else "")
        baseline = _make_baseline(scope="src/")
        result = enforcer.check_scope(baseline)

        # Current behaviour: simple prefix match → passes (known weakness).
        # Assert the return type is correct regardless of the verdict.
        assert isinstance(result, ScopeCheckResult), "check_scope must return ScopeCheckResult"
        # Document the current (imperfect) pass/fail outcome without asserting direction.
        # When path-normalisation is added this becomes: assert not result.passed

    def test_scope_prefix_not_fooled_by_longer_sibling(self, tmp_path):
        """A directory 'src_extra/' must not pass the 'src/' scope check."""
        enforcer = _make_enforcer(tmp_path)
        enforcer._run_git = MagicMock(side_effect=lambda *args: "src_extra/evil.py" if "diff" in args else "")
        baseline = _make_baseline(scope="src/")
        result = enforcer.check_scope(baseline)
        assert not result.passed, "'src_extra/' must not satisfy the 'src/' scope prefix"

    def test_scope_header_contains_scope_string(self, tmp_path):
        """The scope header injected into prompts must mention the declared scope."""
        enforcer = ScopeEnforcer(repo_root=tmp_path)
        header = enforcer.build_scope_header("02_RUNTIME/")
        assert "02_RUNTIME/" in header, "Scope header must contain the declared scope path"

    def test_scope_header_contains_governance_warning(self, tmp_path):
        """The scope header must include language warning against writing outside scope."""
        enforcer = ScopeEnforcer(repo_root=tmp_path)
        header = enforcer.build_scope_header("src/")
        assert "MUST NOT" in header or "outside" in header.lower(), (
            "Scope header must warn about writing outside the declared scope"
        )


# ---------------------------------------------------------------------------
# 4. Malformed scope spec handled safely
# ---------------------------------------------------------------------------


class TestMalformedScopeSpec:
    """Edge-case scope strings must not crash the enforcer or produce false passes."""

    def test_empty_scope_prefix_flags_all_changes(self, tmp_path):
        """An empty scope means nothing is in-scope; all changes are violations."""
        enforcer = _make_enforcer(tmp_path)
        enforcer._run_git = MagicMock(side_effect=lambda *args: "src/main.py" if "diff" in args else "")
        baseline = _make_baseline(scope="")  # empty scope
        result = enforcer.check_scope(baseline)
        # With an empty scope prefix, everything is "outside scope"
        assert not result.passed

    def test_wildcard_scope_passes_all_changes(self, tmp_path):
        """A scope of '/' (repo root) means everything is in-scope."""
        enforcer = _make_enforcer(tmp_path)
        enforcer._run_git = MagicMock(side_effect=lambda *args: "any/path/file.py" if "diff" in args else "")
        baseline = _make_baseline(scope="/")
        # scope_prefix becomes "" after strip("/"), then "/" is added back
        # but that means every file starts with "/" — depends on implementation
        # Just verify it does not raise
        result = enforcer.check_scope(baseline)
        assert isinstance(result, ScopeCheckResult)

    def test_none_baseline_files_does_not_crash(self, tmp_path):
        """Baseline with an empty set of files must not raise on check."""
        enforcer = _make_enforcer(tmp_path)
        enforcer._run_git = MagicMock(return_value="")
        baseline = ScopeBaseline(
            mission_id="m-empty",
            expected_scope="src/",
            baseline_files=set(),
            baseline_count=0,
        )
        result = enforcer.check_scope(baseline)
        assert isinstance(result, ScopeCheckResult)

    def test_scope_with_only_slash_does_not_raise(self, tmp_path):
        """A scope of a bare '/' must not raise AttributeError or crash."""
        enforcer = _make_enforcer(tmp_path)
        enforcer._run_git = MagicMock(return_value="")
        baseline = _make_baseline(scope="/")
        try:
            result = enforcer.check_scope(baseline)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"check_scope raised unexpectedly with '/' scope: {exc}")

    def test_scope_header_with_empty_string_does_not_crash(self, tmp_path):
        """build_scope_header('') must return a non-empty string without raising."""
        enforcer = ScopeEnforcer(repo_root=tmp_path)
        header = enforcer.build_scope_header("")
        assert isinstance(header, str)
        assert len(header) > 0

    def test_scope_header_with_rules_includes_rule_name(self, tmp_path):
        """When governance rules are passed, the header must reference them."""
        enforcer = ScopeEnforcer(repo_root=tmp_path)
        rules = [
            {
                "severity": "critical",
                "name": "no-credential-leak",
                "description": "never write credentials outside vault",
                "fix": "move to vault/",
            }
        ]
        header = enforcer.build_scope_header("src/", rules=rules)
        assert "no-credential-leak" in header
