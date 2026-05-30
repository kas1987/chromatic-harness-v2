"""Tests for the GitHub session-collision guard (no network — runners injected)."""

import json
import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[1] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from concurrency.github_collision import (  # noqa: E402
    OPEN_PR,
    PUSH,
    check_github_collision,
)


def _gh(map_):
    """Build a fake gh runner keyed by a substring of the command."""

    def run(cmd):
        joined = " ".join(cmd)
        for key, (code, payload) in map_.items():
            if key in joined:
                out = payload if isinstance(payload, str) else json.dumps(payload)
                return code, out
        return 0, "[]"

    return run


def _git_clean(cmd):
    # No remote-ahead: rev-list count == 0
    if "rev-list" in cmd:
        return 0, "0"
    return 0, ""


def _git_ahead(n):
    def run(cmd):
        if "rev-list" in cmd:
            return 0, str(n)
        return 0, ""

    return run


class TestRemoteAhead:
    def test_push_blocks_non_fast_forward(self):
        v = check_github_collision(
            branch="feat/x", action=PUSH, gh_runner=_gh({}), git_runner=_git_ahead(3)
        )
        assert v.blocked
        assert any(b["kind"] == "non_fast_forward" for b in v.hard_blocks)

    def test_force_overwrite_is_hard_block(self):
        v = check_github_collision(
            branch="feat/x",
            action=PUSH,
            force=True,
            gh_runner=_gh({}),
            git_runner=_git_ahead(2),
        )
        assert any(b["kind"] == "force_overwrite" for b in v.hard_blocks)

    def test_clean_remote_ok(self):
        v = check_github_collision(
            branch="feat/x", action=PUSH, gh_runner=_gh({}), git_runner=_git_clean
        )
        assert v.decision == "ok"


class TestOpenPr:
    def test_open_pr_duplicate_hard_blocks(self):
        gh = _gh({"pr list": (0, [{"number": 7, "url": "u", "headRefName": "feat/x"}])})
        v = check_github_collision(
            branch="feat/x", action=OPEN_PR, gh_runner=gh, git_runner=_git_clean
        )
        assert v.blocked
        assert v.hard_blocks[0]["kind"] == "duplicate_pr"

    def test_push_with_open_pr_is_soft(self):
        gh = _gh({"pr list": (0, [{"number": 7, "url": "u"}])})
        v = check_github_collision(
            branch="feat/x", action=PUSH, gh_runner=gh, git_runner=_git_clean
        )
        assert not v.blocked
        assert any(w["kind"] == "pr_in_flight" for w in v.soft_warnings)


class TestActions:
    def test_in_flight_actions_soft_warn_on_push(self):
        gh = _gh(
            {
                "run list": (
                    0,
                    [{"databaseId": 1, "status": "in_progress", "workflowName": "ci"}],
                )
            }
        )
        v = check_github_collision(
            branch="feat/x", action=PUSH, gh_runner=gh, git_runner=_git_clean
        )
        assert v.decision == "warn"
        assert any(w["kind"] == "actions_in_flight" for w in v.soft_warnings)

    def test_in_flight_actions_hard_block_on_force(self):
        gh = _gh(
            {
                "run list": (
                    0,
                    [{"databaseId": 1, "status": "queued", "workflowName": "ci"}],
                )
            }
        )
        v = check_github_collision(
            branch="feat/x",
            action=PUSH,
            force=True,
            gh_runner=gh,
            git_runner=_git_clean,
        )
        assert any(b["kind"] == "actions_force_conflict" for b in v.hard_blocks)


class TestFailOpen:
    def test_gh_unavailable_is_soft_not_hard(self):
        def gh_fail(cmd):
            return 127, "gh: not found"

        v = check_github_collision(
            branch="feat/x", action=OPEN_PR, gh_runner=gh_fail, git_runner=_git_clean
        )
        assert not v.blocked
        assert any(w["kind"] == "gh_unverified" for w in v.soft_warnings)


class TestIssueOwnership:
    def test_assigned_issue_soft_warns(self):
        gh = _gh(
            {
                "issue list": (
                    0,
                    [
                        {
                            "number": 9,
                            "title": "t",
                            "assignees": [{"login": "bob"}],
                            "url": "u",
                        }
                    ],
                )
            }
        )
        v = check_github_collision(
            branch="feat/x",
            action=PUSH,
            bead_id="chr-9",
            gh_runner=gh,
            git_runner=_git_clean,
        )
        assert any(w["kind"] == "issue_owned" for w in v.soft_warnings)


def test_invalid_action_raises():
    import pytest

    with pytest.raises(ValueError):
        check_github_collision(branch="x", action="merge")
