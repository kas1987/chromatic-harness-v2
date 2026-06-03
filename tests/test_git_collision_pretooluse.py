"""Tests for the PreToolUse collision hook (git push / gh pr create gating)."""

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_HOOK = _REPO / "scripts" / "hooks" / "git_collision_pretooluse.py"


def _run_hook(payload: dict, env_extra: dict | None = None):
    env = {"PYTHONPATH": str(_REPO / "02_RUNTIME")}
    import os

    full_env = {**os.environ, **env}
    if env_extra:
        full_env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=full_env,
        timeout=30,
    )
    return proc


def test_non_bash_tool_allows():
    p = _run_hook({"tool_name": "Read", "tool_input": {"file_path": "x"}})
    assert p.returncode == 0


def test_unrelated_bash_allows():
    p = _run_hook({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
    assert p.returncode == 0


def test_disabled_via_env_allows():
    p = _run_hook(
        {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}},
        env_extra={"CHROMATIC_NO_COLLISION_HOOK": "1"},
    )
    assert p.returncode == 0


def test_cross_repo_cd_fails_open():
    # A `cd <other-repo> && gh pr create` must NOT be judged against this repo.
    p = _run_hook(
        {
            "tool_name": "Bash",
            "tool_input": {"command": 'cd "C:/Users/kas41/some-other-repo" && gh pr create --title x'},
        }
    )
    assert p.returncode == 0


def test_malformed_stdin_allows():
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input="{not json",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0


def test_push_command_is_recognized_and_fails_open_on_clean():
    # Push is allowed (exit 0) when overridden or when there is no collision.
    # CHROMATIC_ALLOW_COLLISION=1 makes this resilient to CI timing (origin may
    # be ahead of the runner's checkout when tests run mid-flight push).
    p = _run_hook(
        {"tool_name": "Bash", "tool_input": {"command": "git push origin HEAD"}},
        env_extra={"CHROMATIC_ALLOW_COLLISION": "1"},
    )
    assert p.returncode == 0


def test_hard_block_returns_exit_2(monkeypatch, capsys):
    """In-process: a hard collision must block (exit 2) with a reason on stderr."""
    import importlib.util
    import io

    spec = importlib.util.spec_from_file_location("collision_hook", _HOOK)
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)

    from concurrency.github_collision import CollisionVerdict

    blocked = CollisionVerdict(action="push", branch="feat/x")
    blocked.hard_blocks.append({"kind": "non_fast_forward", "detail": "remote ahead"})

    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "feat/x")
    monkeypatch.setattr(
        "concurrency.github_collision.check_github_collision",
        lambda **kw: blocked,
    )
    monkeypatch.setattr(
        hook.sys,
        "stdin",
        io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin x"}})),
    )
    assert hook.main() == 2
    assert "BLOCKED" in capsys.readouterr().err


def _run_hook_inproc(monkeypatch, capsys, kind, *, strict=False):
    import importlib.util
    import io

    spec = importlib.util.spec_from_file_location("collision_hook_x", _HOOK)
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    from concurrency.github_collision import CollisionVerdict

    v = CollisionVerdict(action="push", branch="feat/x")
    v.hard_blocks.append({"kind": kind, "detail": f"{kind} detail"})
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "feat/x")
    monkeypatch.setattr("concurrency.github_collision.check_github_collision", lambda **kw: v)
    if strict:
        monkeypatch.setenv("CHROMATIC_COLLISION_STRICT", "1")
    monkeypatch.setattr(
        hook.sys,
        "stdin",
        io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin x"}})),
    )
    return hook.main()


def test_non_destructive_collision_is_advisory_not_block(monkeypatch, capsys):
    # duplicate_pr / actions_in_flight are NOT destructive → warn + allow (exit 0).
    assert _run_hook_inproc(monkeypatch, capsys, "duplicate_pr") == 0
    assert "[collision][warn]" in capsys.readouterr().err


def test_strict_env_blocks_any_collision(monkeypatch, capsys):
    assert _run_hook_inproc(monkeypatch, capsys, "duplicate_pr", strict=True) == 2


def test_destructive_still_blocks_by_default(monkeypatch, capsys):
    assert _run_hook_inproc(monkeypatch, capsys, "non_fast_forward") == 2


def test_payload_cwd_outside_repo_fails_open():
    """Explicit payload cwd pointing at a different repo → fail-open (exit 0)."""
    p = _run_hook(
        {
            "tool_name": "Bash",
            "tool_input": {
                "command": "gh pr create --title x",
                "cwd": "C:/Users/kas41/some-other-repo",
            },
        }
    )
    assert p.returncode == 0


def test_quoted_git_push_in_argument_does_not_trigger():
    """A literal 'git push' inside a quoted argument (e.g. a commit/reply body) must
    not trigger the gate — only real command tokens count."""
    p = _run_hook(
        {
            "tool_name": "Bash",
            "tool_input": {
                "command": 'gh api repos/x/y/pulls/1/comments -f body="fixed the git push collision"',
            },
        }
    )
    assert p.returncode == 0


def test_leading_cd_wins_over_payload_cwd():
    """`cd <other-repo> && git push` with payload cwd = harness must fail-open:
    the cd target is where the command actually runs, so it overrides payload cwd."""
    import os

    p = _run_hook(
        {
            "tool_name": "Bash",
            "tool_input": {
                "command": 'cd "C:/Users/kas41/some-other-repo" && git push origin HEAD',
                "cwd": os.getcwd(),  # harness repo
            },
        }
    )
    assert p.returncode == 0


def test_camelcase_toolinput_cwd_honored():
    """camelCase toolInput.cwd pointing at another repo → fail-open (parity with snake_case)."""
    p = _run_hook(
        {
            "toolName": "Bash",
            "toolInput": {
                "command": "gh pr create --title x",
                "cwd": "C:/Users/kas41/some-other-repo",
            },
        }
    )
    assert p.returncode == 0


def test_payload_cwd_field_at_toplevel_fails_open():
    """payload.cwd (top-level) pointing at a different repo → fail-open."""
    p = _run_hook(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "git push origin HEAD"},
            "cwd": "C:/Users/kas41/some-other-repo",
        }
    )
    assert p.returncode == 0


def test_check_github_collision_accepts_cwd_kwarg():
    """check_github_collision must accept cwd= without raising."""
    import sys

    sys.path.insert(0, str(_REPO / "02_RUNTIME"))
    from concurrency.github_collision import PUSH, check_github_collision

    fake_results: list = []

    def fake_git(cmd):
        fake_results.append(cmd)
        return 1, ""

    def fake_gh(cmd):
        fake_results.append(cmd)
        return 0, "[]"

    v = check_github_collision(
        branch="feat/test",
        action=PUSH,
        cwd="/tmp/fake-repo",
        gh_runner=fake_gh,
        git_runner=fake_git,
    )
    assert v.action == PUSH
    assert v.branch == "feat/test"


def test_override_allows_hard_block(monkeypatch):
    import importlib.util
    import io

    spec = importlib.util.spec_from_file_location("collision_hook2", _HOOK)
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)

    from concurrency.github_collision import CollisionVerdict

    blocked = CollisionVerdict(action="push", branch="feat/x")
    blocked.hard_blocks.append({"kind": "non_fast_forward", "detail": "remote ahead"})
    monkeypatch.setattr(hook, "_current_branch", lambda cwd=None: "feat/x")
    monkeypatch.setattr("concurrency.github_collision.check_github_collision", lambda **kw: blocked)
    monkeypatch.setenv("CHROMATIC_ALLOW_COLLISION", "1")
    monkeypatch.setattr(
        hook.sys,
        "stdin",
        io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin x"}})),
    )
    assert hook.main() == 0
