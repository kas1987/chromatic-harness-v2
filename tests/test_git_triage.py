"""Tests for git failure classification and triage intake."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from activity.git_triage import classify_git_failure, triage_git_failure  # noqa: E402
from intake.queue import list_queued  # noqa: E402
import workflows.run_log as run_log_mod  # noqa: E402


@pytest.mark.parametrize(
    "stderr,step,expected",
    [
        (
            "error: cannot pull with rebase: You have unstaged changes",
            "git pull",
            "rebase_blocked",
        ),
        (".beads/issues.jsonl modified", "rebase", "unstaged_generated"),
        ("remote rejected", "git push", "push_rejected"),
        ("pre-commit hook failed", "commit", "commit_hook"),
        ("pytest failed", "pre-push", "test_fail"),
    ],
)
def test_classify_git_failure(stderr: str, step: str, expected: str):
    assert classify_git_failure(stderr, step) == expected


def test_triage_writes_digest_and_intake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    wf = tmp_path / "docs" / "workflows" / "WORKFLOW_RUN_LOG.jsonl"
    monkeypatch.setattr(run_log_mod, "runtime_log_path", lambda _r: wf)
    monkeypatch.setattr(run_log_mod, "default_log_path", lambda _r: wf)

    steps = [
        {
            "cmd": ["git", "pull", "--rebase"],
            "status": "failed",
            "stderr": "cannot pull with rebase: unstaged changes in .beads/issues.jsonl",
        }
    ]
    result = triage_git_failure(
        tmp_path,
        steps=steps,
        bead_id="chromatic-harness-v2-git1",
        lane="human",
    )
    assert result.failure_class == "unstaged_generated"
    digest = tmp_path / result.digest_path
    assert digest.is_file()
    assert "Git triage" in digest.read_text(encoding="utf-8")

    queue = tmp_path / "07_LOGS_AND_AUDIT" / "intake_queue.jsonl"
    queued = list_queued(path=queue, repo_root=tmp_path)
    assert len(queued) >= 2
    lanes = {e.lane for e in queued}
    assert "human" in lanes
    assert "agent" in lanes
