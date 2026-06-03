"""Tests for workflows.git_automation — git pipeline runner helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from workflows.git_automation import (
    GitRunResult,
    _detect_secrets_in_changes,
    _gh_available,
    _git_status_porcelain,
    _has_staged_changes,
    _is_secret_path,
    _open_pr_exists,
    _protected_branch,
    _run,
    run_git_pipeline,
)
from workflows.git_policy import GitPipelineDecision


# ---------------------------------------------------------------------------
# _is_secret_path
# ---------------------------------------------------------------------------


class TestIsSecretPath:
    def test_env_file_is_secret(self):
        assert _is_secret_path(".env") is True

    def test_env_with_extension_is_secret(self):
        assert _is_secret_path(".env.production") is True

    def test_credentials_json_is_secret(self):
        assert _is_secret_path("credentials.json") is True

    def test_pem_file_is_secret(self):
        assert _is_secret_path("server.pem") is True

    def test_id_rsa_is_secret(self):
        assert _is_secret_path("id_rsa") is True

    def test_key_file_is_secret(self):
        assert _is_secret_path("private.key") is True

    def test_env_example_not_secret(self):
        assert _is_secret_path(".env.example") is False

    def test_env_sample_not_secret(self):
        assert _is_secret_path(".env.sample") is False

    def test_env_template_not_secret(self):
        assert _is_secret_path(".env.template") is False

    def test_regular_python_file_not_secret(self):
        assert _is_secret_path("src/main.py") is False

    def test_backslash_path_normalised(self):
        assert _is_secret_path("config\\credentials.json") is True

    def test_uppercase_extension_detected(self):
        assert _is_secret_path("SERVER.PEM") is True


# ---------------------------------------------------------------------------
# _protected_branch
# ---------------------------------------------------------------------------


class TestProtectedBranch:
    def test_main_is_protected(self):
        assert _protected_branch("main") is True

    def test_master_is_protected(self):
        assert _protected_branch("master") is True

    def test_feature_branch_not_protected(self):
        assert _protected_branch("feature/my-work") is False

    def test_develop_not_protected(self):
        assert _protected_branch("develop") is False


# ---------------------------------------------------------------------------
# _run
# ---------------------------------------------------------------------------


class TestRun:
    def test_dry_run_returns_dry_run_status(self, tmp_path):
        result = _run(["echo", "hello"], tmp_path, dry_run=True)
        assert result["status"] == "dry_run"
        assert result["cmd"] == ["echo", "hello"]
        assert result["stdout"] == ""

    def test_real_run_ok(self, tmp_path):
        result = _run(["true"], tmp_path, dry_run=False)
        assert result["status"] == "ok"
        assert result["returncode"] == 0

    def test_real_run_failed_nonzero(self, tmp_path):
        result = _run(["false"], tmp_path, dry_run=False)
        assert result["status"] == "failed"
        assert result["returncode"] != 0

    def test_stdout_truncated_to_2000(self, tmp_path):
        # produce more than 2000 chars of output
        long_str = "x" * 3000
        result = _run(["sh", "-c", f"echo '{long_str}'"], tmp_path, dry_run=False)
        assert len(result["stdout"]) <= 2001  # newline may be included


# ---------------------------------------------------------------------------
# _git_status_porcelain
# ---------------------------------------------------------------------------


class TestGitStatusPorcelain:
    def test_returns_string(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.stdout = "M  changed.py\n"
            mock_run.return_value = mock_proc
            result = _git_status_porcelain(tmp_path)
        assert "changed.py" in result

    def test_returns_empty_when_no_output(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.stdout = None
            mock_run.return_value = mock_proc
            result = _git_status_porcelain(tmp_path)
        assert result == ""


# ---------------------------------------------------------------------------
# _has_staged_changes
# ---------------------------------------------------------------------------


class TestHasStagedChanges:
    def test_true_when_modified_staged(self, tmp_path):
        with patch("workflows.git_automation._git_status_porcelain", return_value="M  foo.py\n"):
            assert _has_staged_changes(tmp_path) is True

    def test_true_when_added_staged(self, tmp_path):
        with patch("workflows.git_automation._git_status_porcelain", return_value="A  bar.py\n"):
            assert _has_staged_changes(tmp_path) is True

    def test_false_when_only_untracked(self, tmp_path):
        # untracked files begin with '??' in porcelain, first char is '?'
        with patch("workflows.git_automation._git_status_porcelain", return_value="?? untracked.py\n"):
            assert _has_staged_changes(tmp_path) is False

    def test_false_when_empty(self, tmp_path):
        with patch("workflows.git_automation._git_status_porcelain", return_value=""):
            assert _has_staged_changes(tmp_path) is False


# ---------------------------------------------------------------------------
# _gh_available
# ---------------------------------------------------------------------------


class TestGhAvailable:
    def test_true_when_gh_returns_zero(self):
        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_run.return_value = mock_proc
            assert _gh_available() is True

    def test_false_when_gh_returns_nonzero(self):
        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_run.return_value = mock_proc
            assert _gh_available() is False

    def test_false_when_file_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert _gh_available() is False


# ---------------------------------------------------------------------------
# _open_pr_exists
# ---------------------------------------------------------------------------


class TestOpenPrExists:
    def test_false_when_gh_unavailable(self, tmp_path):
        with patch("workflows.git_automation._gh_available", return_value=False):
            assert _open_pr_exists(tmp_path, "feat/x") is False

    def test_false_when_empty_list(self, tmp_path):
        with patch("workflows.git_automation._gh_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_proc = MagicMock()
                mock_proc.returncode = 0
                mock_proc.stdout = "[]"
                mock_run.return_value = mock_proc
                assert _open_pr_exists(tmp_path, "feat/x") is False

    def test_true_when_pr_list_nonempty(self, tmp_path):
        with patch("workflows.git_automation._gh_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_proc = MagicMock()
                mock_proc.returncode = 0
                mock_proc.stdout = '[{"number":1}]'
                mock_run.return_value = mock_proc
                assert _open_pr_exists(tmp_path, "feat/x") is True


# ---------------------------------------------------------------------------
# GitRunResult.to_dict
# ---------------------------------------------------------------------------


class TestGitRunResult:
    def _make_decision(self) -> GitPipelineDecision:
        return GitPipelineDecision(
            commit=False,
            push=False,
            open_pr=False,
            merge=False,
            reasons={op: "test" for op in ("commit", "push", "open_pr", "merge")},
        )

    def test_to_dict_has_expected_keys(self, tmp_path):
        result = GitRunResult(dry_run=True, decision=self._make_decision(), steps=[])
        d = result.to_dict()
        assert "dry_run" in d
        assert "pipeline" in d
        assert "steps" in d
        assert "git_backend" in d

    def test_dry_run_flag_reflected(self, tmp_path):
        result = GitRunResult(dry_run=True, decision=self._make_decision(), steps=[])
        assert result.to_dict()["dry_run"] is True

    def test_error_default_empty(self):
        result = GitRunResult(dry_run=False, decision=self._make_decision(), steps=[])
        assert result.error == ""


# ---------------------------------------------------------------------------
# run_git_pipeline — dry-run / smoke tests
# ---------------------------------------------------------------------------


class TestRunGitPipeline:
    def _patch_env(self, monkeypatch, tmp_path):
        """Patch all subprocess calls so the pipeline runs in isolation."""
        monkeypatch.setattr("workflows.git_automation._current_branch", lambda _: "feat/test")
        monkeypatch.setattr("workflows.git_automation._detect_secrets_in_changes", lambda _: False)
        monkeypatch.setattr("workflows.git_automation._has_staged_changes", lambda _: True)
        monkeypatch.setattr("workflows.git_automation._protected_branch", lambda _: False)
        monkeypatch.setattr("workflows.git_automation._gh_available", lambda: False)
        monkeypatch.setattr("workflows.git_automation._ci_passed_for_branch", lambda *a: False)

    def test_dry_run_returns_result(self, tmp_path, monkeypatch):
        self._patch_env(monkeypatch, tmp_path)
        result = run_git_pipeline(
            tmp_path,
            confidence=99,
            risk_level="low",
            verifier_approved=True,
            tests_passed=True,
            dry_run=True,
        )
        assert isinstance(result, GitRunResult)
        assert result.dry_run is True

    def test_dry_run_steps_have_dry_run_status(self, tmp_path, monkeypatch):
        self._patch_env(monkeypatch, tmp_path)
        result = run_git_pipeline(
            tmp_path,
            confidence=99,
            risk_level="low",
            verifier_approved=True,
            tests_passed=True,
            dry_run=True,
        )
        run_steps = [s for s in result.steps if s.get("status") == "dry_run"]
        assert len(run_steps) >= 2  # at least commit+add

    def test_secrets_detected_skips_all(self, tmp_path, monkeypatch):
        monkeypatch.setattr("workflows.git_automation._current_branch", lambda _: "feat/test")
        monkeypatch.setattr("workflows.git_automation._detect_secrets_in_changes", lambda _: True)
        monkeypatch.setattr("workflows.git_automation._has_staged_changes", lambda _: True)
        monkeypatch.setattr("workflows.git_automation._protected_branch", lambda _: False)
        monkeypatch.setattr("workflows.git_automation._gh_available", lambda: False)
        monkeypatch.setattr("workflows.git_automation._ci_passed_for_branch", lambda *a: False)
        result = run_git_pipeline(
            tmp_path,
            confidence=99,
            risk_level="low",
            verifier_approved=True,
            tests_passed=True,
            dry_run=True,
        )
        assert result.decision.commit is False
        assert result.decision.push is False

    def test_low_confidence_skips_all(self, tmp_path, monkeypatch):
        self._patch_env(monkeypatch, tmp_path)
        result = run_git_pipeline(
            tmp_path,
            confidence=10,
            risk_level="low",
            verifier_approved=False,
            tests_passed=False,
            dry_run=True,
        )
        assert result.decision.commit is False

    def test_commit_message_used(self, tmp_path, monkeypatch):
        self._patch_env(monkeypatch, tmp_path)
        # bead_id must be non-empty so the msg expression evaluates to commit_message
        result = run_git_pipeline(
            tmp_path,
            confidence=99,
            risk_level="low",
            verifier_approved=True,
            tests_passed=True,
            bead_id="BID-1",
            commit_message="custom commit msg",
            dry_run=True,
        )
        # In dry_run mode, commit step has cmd list containing the message
        commit_steps = [s for s in result.steps if isinstance(s.get("cmd"), list) and "commit" in s["cmd"]]
        if commit_steps:
            assert "custom commit msg" in commit_steps[0]["cmd"]
