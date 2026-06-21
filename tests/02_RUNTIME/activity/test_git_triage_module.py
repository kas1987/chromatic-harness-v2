"""Tests for activity/git_triage.py — boost coverage from 21% to 70%+."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from activity.git_triage import (
    FAILURE_CLASSES,
    TriageResult,
    _digest_bullets,
    _failed_steps_summary,
    _write_digest,
    classify_git_failure,
)


# ---------------------------------------------------------------------------
# classify_git_failure
# ---------------------------------------------------------------------------


class TestClassifyGitFailure:
    def test_secrets_from_env(self):
        assert classify_git_failure("secret detected in .env", "git commit") == "secrets"

    def test_secrets_from_keyword(self):
        assert classify_git_failure("found secret token in file") == "secrets"

    def test_test_fail_from_pytest(self):
        assert classify_git_failure("pytest failed", "pre-push hook") == "test_fail"

    def test_commit_hook_from_pre_commit(self):
        assert classify_git_failure("pre-commit hook failed") == "commit_hook"

    def test_commit_hook_from_hook_fail(self):
        assert classify_git_failure("hook failed during check", "hook") == "commit_hook"

    def test_push_rejected(self):
        assert classify_git_failure("rejected by remote", "git push") == "push_rejected"

    def test_permission_denied_push(self):
        assert classify_git_failure("permission denied to push") == "push_rejected"

    def test_unstaged_generated_beads(self):
        assert classify_git_failure("untracked file: .beads/issues.jsonl") == "unstaged_generated"

    def test_unstaged_generated_snapshot(self):
        assert classify_git_failure("changes to inventory.snapshot not staged") == "unstaged_generated"

    def test_unstaged_generated_latest_json(self):
        assert classify_git_failure("modified: latest.json") == "unstaged_generated"

    def test_rebase_blocked_cannot_pull(self):
        assert classify_git_failure("cannot pull with rebase: unstaged changes") == "rebase_blocked"

    def test_rebase_blocked_conflict(self):
        assert classify_git_failure("conflict in merge fail") == "rebase_blocked"

    def test_unstaged_overwritten(self):
        assert classify_git_failure("would be overwritten by merge") == "unstaged_generated"

    def test_unknown_fallback(self):
        assert classify_git_failure("some random unrecognized error") == "unknown"

    def test_failure_classes_completeness(self):
        assert FAILURE_CLASSES == frozenset(
            {
                "unstaged_generated",
                "rebase_blocked",
                "commit_hook",
                "push_rejected",
                "test_fail",
                "secrets",
                "unknown",
            }
        )


# ---------------------------------------------------------------------------
# _failed_steps_summary
# ---------------------------------------------------------------------------


class TestFailedStepsSummary:
    def test_empty_steps_returns_empty(self):
        combined, step_name = _failed_steps_summary([])
        assert combined == ""
        assert step_name == ""

    def test_skips_non_failed_steps(self):
        steps = [{"status": "ok", "cmd": "git add", "stderr": ""}]
        combined, _ = _failed_steps_summary(steps)
        assert combined == ""

    def test_includes_failed_steps(self):
        steps = [{"status": "failed", "cmd": "git commit", "stderr": "hook rejected"}]
        combined, _ = _failed_steps_summary(steps)
        assert "git commit" in combined
        assert "hook rejected" in combined

    def test_step_name_from_last_failed_cmd_list(self):
        steps = [
            {"status": "ok", "cmd": ["git", "add"]},
            {"status": "failed", "cmd": ["git", "push"], "stderr": ""},
        ]
        _, step_name = _failed_steps_summary(steps)
        assert step_name == "git push"

    def test_step_name_from_last_failed_cmd_str(self):
        steps = [{"status": "failed", "cmd": "git commit", "stderr": ""}]
        _, step_name = _failed_steps_summary(steps)
        assert step_name == "git commit"

    def test_multiple_failed_steps_joined(self):
        steps = [
            {"status": "failed", "cmd": "step1", "stderr": "err1"},
            {"status": "failed", "cmd": "step2", "stderr": "err2"},
        ]
        combined, _ = _failed_steps_summary(steps)
        assert "err1" in combined
        assert "err2" in combined
        assert "---" in combined

    def test_uses_step_key_as_fallback_for_cmd(self):
        steps = [{"status": "failed", "step": "validate", "stderr": ""}]
        combined, _ = _failed_steps_summary(steps)
        assert "validate" in combined

    def test_uses_reason_as_fallback_for_stderr(self):
        steps = [{"status": "failed", "cmd": "check", "reason": "timeout"}]
        combined, _ = _failed_steps_summary(steps)
        assert "timeout" in combined


# ---------------------------------------------------------------------------
# _digest_bullets
# ---------------------------------------------------------------------------


class TestDigestBullets:
    def test_unstaged_generated_bullets(self):
        bullets = _digest_bullets("unstaged_generated", "")
        assert len(bullets) > 0
        assert any("generated" in b.lower() or "gitignore" in b.lower() for b in bullets)

    def test_rebase_blocked_bullets(self):
        bullets = _digest_bullets("rebase_blocked", "")
        assert len(bullets) > 0
        assert any("rebase" in b.lower() or "stash" in b.lower() for b in bullets)

    def test_commit_hook_bullets(self):
        bullets = _digest_bullets("commit_hook", "")
        assert len(bullets) > 0
        assert any("pytest" in b.lower() or "hook" in b.lower() for b in bullets)

    def test_test_fail_bullets(self):
        bullets = _digest_bullets("test_fail", "")
        assert len(bullets) > 0
        assert any("test" in b.lower() or "fix" in b.lower() for b in bullets)

    def test_secrets_bullets(self):
        bullets = _digest_bullets("secrets", "")
        assert len(bullets) > 0
        assert any("secret" in b.lower() or "rotate" in b.lower() for b in bullets)

    def test_push_rejected_bullets(self):
        bullets = _digest_bullets("push_rejected", "")
        assert len(bullets) > 0
        assert any("push" in b.lower() or "permission" in b.lower() or "pr" in b.lower() for b in bullets)

    def test_unknown_bullets_fallback(self):
        bullets = _digest_bullets("unknown", "")
        assert len(bullets) > 0
        assert any("inspect" in b.lower() or "bead" in b.lower() for b in bullets)


# ---------------------------------------------------------------------------
# TriageResult
# ---------------------------------------------------------------------------


class TestTriageResult:
    def test_to_dict_has_required_keys(self):
        r = TriageResult(failure_class="test_fail", digest_path="path/to/digest.md")
        d = r.to_dict()
        assert d["failure_class"] == "test_fail"
        assert d["digest_path"] == "path/to/digest.md"
        assert d["intake_ids"] == []
        assert d["agent_intake_id"] == ""

    def test_to_dict_with_intake_ids(self):
        r = TriageResult(
            failure_class="secrets",
            digest_path="p",
            intake_ids=["abc", "def"],
            agent_intake_id="xyz",
        )
        d = r.to_dict()
        assert d["intake_ids"] == ["abc", "def"]
        assert d["agent_intake_id"] == "xyz"


# ---------------------------------------------------------------------------
# _write_digest
# ---------------------------------------------------------------------------


class TestWriteDigest:
    def test_creates_file_in_sessions_dir(self, tmp_path: Path):
        path = _write_digest(
            tmp_path,
            failure_class="test_fail",
            bead_id="bd-123",
            steps=[{"status": "failed", "cmd": "pytest", "stderr": "AssertionError"}],
            stderr_summary="AssertionError in test_foo",
        )
        assert path.is_file()
        assert "sessions" in str(path)
        assert path.name.startswith("git-triage-")

    def test_digest_contains_failure_class(self, tmp_path: Path):
        path = _write_digest(
            tmp_path,
            failure_class="secrets",
            bead_id="",
            steps=[],
            stderr_summary="secret found",
        )
        content = path.read_text(encoding="utf-8")
        assert "secrets" in content

    def test_digest_contains_bead_id(self, tmp_path: Path):
        path = _write_digest(
            tmp_path,
            failure_class="unknown",
            bead_id="bead-xyz",
            steps=[],
            stderr_summary="",
        )
        content = path.read_text(encoding="utf-8")
        assert "bead-xyz" in content

    def test_digest_none_bead_fallback(self, tmp_path: Path):
        path = _write_digest(
            tmp_path,
            failure_class="unknown",
            bead_id="",
            steps=[],
            stderr_summary="",
        )
        content = path.read_text(encoding="utf-8")
        assert "none" in content

    def test_digest_truncated_at_8000(self, tmp_path: Path):
        long_stderr = "x" * 10000
        path = _write_digest(
            tmp_path,
            failure_class="unknown",
            bead_id="",
            steps=[],
            stderr_summary=long_stderr,
        )
        content = path.read_text(encoding="utf-8")
        assert len(content) <= 8000
