"""Tests for collision_guard.py — multi-agent collision preflight (bead gl6t).

Network-free: git/bd are not invoked for the pure check builders; inputs injected.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("collision_guard", REPO / "scripts" / "collision_guard.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["collision_guard"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_named_branch_fails_on_shared():
    mod = _load()
    assert mod.check_named_branch("session/chromatic-harness-v2-initial").status == "fail"
    assert mod.check_named_branch("main").status == "fail"
    assert mod.check_named_branch("master").status == "fail"


def test_named_branch_passes_on_feature():
    mod = _load()
    assert mod.check_named_branch("rg-081-go-mode").status == "pass"


def test_named_branch_detached_warns():
    mod = _load()
    assert mod.check_named_branch("").status == "warn"


def test_branch_sharing_fails_when_two_checkouts():
    mod = _load()
    wts = [
        {"path": "/repo", "branch": "feat"},
        {"path": "/wt", "branch": "feat"},
    ]
    assert mod.check_branch_sharing("feat", wts).status == "fail"


def test_branch_sharing_passes_when_exclusive():
    mod = _load()
    wts = [{"path": "/repo", "branch": "feat"}, {"path": "/wt", "branch": "other"}]
    assert mod.check_branch_sharing("feat", wts).status == "pass"


def test_worktree_isolation_pass_in_worktree():
    mod = _load()
    wts = [{"path": "/main", "branch": "session/x"}, {"path": str(REPO), "branch": "feat"}]
    # REPO != main path -> we are in a dedicated worktree
    c = mod.check_worktree_isolation(REPO, wts)
    assert c.status == "pass"


def test_worktree_isolation_warns_on_main_with_others():
    mod = _load()
    wts = [{"path": str(REPO), "branch": "feat"}, {"path": "/other", "branch": "feat2"}]
    c = mod.check_worktree_isolation(REPO, wts)
    assert c.status == "warn"


def test_run_guard_shape_and_overall(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "current_branch", lambda: "feat-x")
    monkeypatch.setattr(mod, "list_worktrees", lambda: [{"path": str(mod.REPO), "branch": "feat-x"}])
    monkeypatch.setattr(mod, "check_clean_index", lambda: mod.Check("clean_index", "pass", "ok"))
    result = mod.run_guard()
    assert result["overall"] in {"pass", "warn", "fail"}
    assert {"branch", "worktree_count", "counts", "checks"} <= set(result)


def test_run_guard_fails_on_shared_branch(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "current_branch", lambda: "main")
    monkeypatch.setattr(mod, "list_worktrees", lambda: [{"path": str(mod.REPO), "branch": "main"}])
    monkeypatch.setattr(mod, "check_clean_index", lambda: mod.Check("clean_index", "pass", "ok"))
    assert mod.run_guard()["overall"] == "fail"  # shared-branch work is blocking


def test_summarize_fail_open(monkeypatch):
    mod = _load()
    monkeypatch.setattr(
        mod, "run_guard", lambda bead_id="": {"overall": "pass", "branch": "b", "worktree_count": 1, "counts": {}}
    )
    s = mod.summarize()
    assert s["status"] == "ok" and s["overall"] == "pass"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
