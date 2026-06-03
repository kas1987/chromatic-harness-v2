"""Worktree-isolation tests for claude_delegate_gate._spawn_claude.

Mirrors tests/test_task_runner.py's worktree tests: the spawned `claude -p`
worker must run inside an isolated `git worktree` (never the shared checkout),
refuse to spawn if the worktree can't be created, and tear the worktree down
afterwards regardless of outcome. No real claude/git is invoked — git and the
worktree helpers are monkeypatched.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    # The module inserts 02_RUNTIME/ and scripts/ on sys.path itself for its imports.
    sys.path.insert(0, str(REPO / "02_RUNTIME"))
    sys.path.insert(0, str(REPO / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "claude_delegate_gate_mod", REPO / "scripts" / "claude_delegate_gate.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["claude_delegate_gate_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


CDG = _load()


# ── worktree path helper ────────────────────────────────────────────────────


def test_worktree_path_sanitizes_worker_id():
    p = CDG._worktree_path("chromatic-harness-v2-bpq.1")
    assert p.name == "delegate-chromatic-harness-v2-bpq_1"
    assert p.parent.name == ".worktrees"


def test_worktree_path_empty_id_falls_back():
    assert CDG._worktree_path("").name == "delegate-delegate"


# ── _spawn_claude isolation ─────────────────────────────────────────────────


def test_spawn_runs_worker_in_worktree_and_cleans_up(tmp_path, monkeypatch):
    wt = tmp_path / ".worktrees" / "delegate-b1"
    monkeypatch.setattr(CDG.shutil, "which", lambda n: "claude")
    monkeypatch.setattr(CDG, "_create_worktree", lambda wid: wt)
    seen: dict = {}

    def fake_run(cmd, timeout=900, cwd=None):
        seen["cwd"] = cwd
        seen["cmd"] = cmd
        return 0, "delegation dispatched"

    monkeypatch.setattr(CDG, "_run", fake_run)
    removed: dict = {}
    monkeypatch.setattr(CDG, "_remove_worktree", lambda p: removed.__setitem__("path", p))

    ok, msg = CDG._spawn_claude(tmp_path / "prompt.md", "b1")
    assert ok is True
    assert seen["cwd"] == wt  # worker ran INSIDE the worktree, not the shared checkout
    assert seen["cmd"][0] == "claude"
    assert removed["path"] == wt  # worktree torn down afterwards


def test_spawn_refuses_when_worktree_creation_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(CDG.shutil, "which", lambda n: "claude")
    monkeypatch.setattr(CDG, "_create_worktree", lambda wid: None)
    called = {"run": False}
    monkeypatch.setattr(CDG, "_run", lambda *a, **k: (called.__setitem__("run", True), (0, ""))[1])

    ok, msg = CDG._spawn_claude(tmp_path / "prompt.md", "b1")
    assert ok is False
    assert "refusing to spawn into the shared checkout" in msg
    assert called["run"] is False  # never touched the shared checkout


def test_spawn_cleans_up_worktree_even_on_worker_failure(tmp_path, monkeypatch):
    wt = tmp_path / ".worktrees" / "delegate-b1"
    monkeypatch.setattr(CDG.shutil, "which", lambda n: "claude")
    monkeypatch.setattr(CDG, "_create_worktree", lambda wid: wt)
    monkeypatch.setattr(CDG, "_run", lambda *a, **k: (1, "boom"))
    removed: dict = {}
    monkeypatch.setattr(CDG, "_remove_worktree", lambda p: removed.__setitem__("path", p))

    ok, msg = CDG._spawn_claude(tmp_path / "prompt.md", "b1")
    assert ok is False
    assert removed["path"] == wt  # cleaned up despite worker failure


def test_spawn_skips_worktree_when_claude_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(CDG.shutil, "which", lambda n: None)
    created = {"called": False}
    monkeypatch.setattr(CDG, "_create_worktree", lambda wid: created.__setitem__("called", True))

    ok, msg = CDG._spawn_claude(tmp_path / "prompt.md", "b1")
    assert ok is False
    assert "claude CLI not found" in msg
    assert created["called"] is False  # no worktree churn when there's nothing to spawn
