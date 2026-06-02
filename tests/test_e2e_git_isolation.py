"""Regression guard: the E2E gate must be git-isolated.

Root cause (fixed here): the git pre-push hook exports ``GIT_DIR=<live>/.git``
into its environment. ``tests/run-all-e2e.py`` spawned pytest subprocesses that
inherited it, so a test running ``git commit`` with ``cwd=tmp_path`` (but no
work-tree override) wrote to the LIVE repo — injecting a stray
``Test <t@example.com> "init" + a.txt`` commit onto the active branch and even
mutating the live ``user.email``.

These tests fail before the fix and pass after it.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TESTS = REPO / "tests"


def _clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _head(repo: Path) -> str:
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo),
        env=_clean_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    return r.stdout.strip()


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_all_e2e", TESTS / "run-all-e2e.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _load_git_snapshots():
    spec = importlib.util.spec_from_file_location("test_git_snapshots", TESTS / "test_git_snapshots.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_runner_clean_env_strips_git_location_vars(monkeypatch):
    """run-all-e2e._clean_env() must drop inherited GIT_* vars."""
    monkeypatch.setenv("GIT_DIR", "/somewhere/.git")
    monkeypatch.setenv("GIT_WORK_TREE", "/somewhere")
    monkeypatch.setenv("GIT_INDEX_FILE", "/somewhere/.git/index")
    runner = _load_runner()
    env = runner._clean_env()
    assert "GIT_DIR" not in env
    assert "GIT_WORK_TREE" not in env
    assert "GIT_INDEX_FILE" not in env
    # Non-git vars must survive.
    assert "PATH" in env


def test_git_fixture_isolated_when_GIT_DIR_points_at_another_repo(tmp_path, monkeypatch):
    """The hermetic fixture must not write to an inherited GIT_DIR.

    Simulates the pre-push hook by pointing GIT_DIR at an 'outer' repo, then
    runs the snapshot suite's _init_repo against a separate 'inner' dir. The
    outer repo's HEAD must be untouched.
    """
    outer = tmp_path / "outer"
    outer.mkdir()
    env = _clean_env()
    subprocess.run(["git", "init", "-q"], cwd=outer, env=env, check=True)
    subprocess.run(["git", "config", "user.email", "outer@example.com"], cwd=outer, env=env, check=True)
    subprocess.run(["git", "config", "user.name", "Outer"], cwd=outer, env=env, check=True)
    (outer / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "seed.txt"], cwd=outer, env=env, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=outer, env=env, check=True)
    outer_head_before = _head(outer)

    # Pre-push hook leaks GIT_DIR into the environment.
    monkeypatch.setenv("GIT_DIR", str(outer / ".git"))

    snapshots = _load_git_snapshots()
    inner = tmp_path / "inner"
    inner.mkdir()
    snapshots._init_repo(inner)  # hardened helper must ignore the leaked GIT_DIR

    outer_head_after = _head(outer)
    assert outer_head_before == outer_head_after, "fixture leaked a commit into the GIT_DIR repo"
    # And the commit must actually be in `inner`.
    inner_head = _head(inner)
    assert inner_head and inner_head != outer_head_before


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
