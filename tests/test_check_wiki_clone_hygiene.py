"""Tests for scripts/check_wiki_clone_hygiene.py — the duplicate-wiki-clone guard.

Uses throwaway git repos under tmp_path with a clean env (no inherited GIT_DIR), so
the harness E2E git-isolation guard stays satisfied.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO / "scripts" / "check_wiki_clone_hygiene.py"
_REMOTE = "kas1987/chromatic-wiki"


def _clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _load():
    spec = importlib.util.spec_from_file_location("check_wiki_clone_hygiene", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _make_clone(path: Path, remote_url: str, *, branch: str = "main") -> Path:
    env = _clean_env()
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", branch], cwd=path, env=env, check=True)
    subprocess.run(["git", "remote", "add", "origin", remote_url], cwd=path, env=env, check=True)
    # Seed a commit so HEAD and origin/HEAD can resolve.
    (path / "README.md").write_text("wiki\n", encoding="utf-8")
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, env=env, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, env=env, check=True)
    subprocess.run(["git", "add", "-A"], cwd=path, env=env, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=path, env=env, check=True)
    # Make origin/HEAD resolvable to `branch` so default-branch detection works.
    subprocess.run(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD", f"refs/remotes/origin/{branch}"],
        cwd=path,
        env=env,
        check=False,
    )
    subprocess.run(
        ["git", "update-ref", f"refs/remotes/origin/{branch}", "HEAD"],
        cwd=path,
        env=env,
        check=False,
    )
    return path


def test_normalize_remote_forms():
    m = _load()
    assert m._normalize_remote("https://github.com/kas1987/chromatic-wiki.git") == _REMOTE
    assert m._normalize_remote("git@github.com:kas1987/chromatic-wiki.git") == _REMOTE
    assert m._normalize_remote("https://github.com/kas1987/chromatic-wiki/") == _REMOTE


def test_single_canonical_clone_passes(tmp_path):
    m = _load()
    root = tmp_path / "drive"
    canonical = _make_clone(root / "chromatic-wiki", f"https://github.com/{_REMOTE}.git")
    report = m.audit(root, canonical, _REMOTE)
    assert report["ok"] is True
    assert report["failures"] == []
    assert len(report["clones"]) == 1


def test_two_clones_fail(tmp_path):
    m = _load()
    root = tmp_path / "drive"
    canonical = _make_clone(root / "chromatic-wiki", f"https://github.com/{_REMOTE}.git")
    _make_clone(root / "Chromatic_Wiki", f"git@github.com:{_REMOTE}.git")  # stale duplicate
    report = m.audit(root, canonical, _REMOTE)
    assert report["ok"] is False
    assert any("clones of" in f for f in report["failures"])
    assert len(report["clones"]) == 2


def test_missing_clone_fails(tmp_path):
    m = _load()
    root = tmp_path / "drive"
    root.mkdir()
    report = m.audit(root, root / "chromatic-wiki", _REMOTE)
    assert report["ok"] is False
    assert any("no local clone" in f for f in report["failures"])


def test_parked_feature_branch_warns(tmp_path):
    m = _load()
    root = tmp_path / "drive"
    canonical = _make_clone(root / "chromatic-wiki", f"https://github.com/{_REMOTE}.git", branch="main")
    env = _clean_env()
    subprocess.run(["git", "checkout", "-q", "-b", "learnings/auto-promote-x"], cwd=canonical, env=env, check=True)
    report = m.audit(root, canonical, _REMOTE)
    assert report["ok"] is True  # warning, not failure
    assert any("default" in w for w in report["warnings"])


def test_retired_clone_is_ignored(tmp_path):
    """A `<name>.RETIRED-<date>` clone is the sanctioned retirement — guard must pass."""
    m = _load()
    root = tmp_path / "drive"
    canonical = _make_clone(root / "chromatic-wiki", f"https://github.com/{_REMOTE}.git")
    _make_clone(root / "Chromatic_Wiki.RETIRED-20260602", f"git@github.com:{_REMOTE}.git")
    report = m.audit(root, canonical, _REMOTE)
    assert report["ok"] is True
    assert len(report["clones"]) == 1


def test_unrelated_repo_ignored(tmp_path):
    m = _load()
    root = tmp_path / "drive"
    canonical = _make_clone(root / "chromatic-wiki", f"https://github.com/{_REMOTE}.git")
    _make_clone(root / "some-other-repo", "https://github.com/kas1987/unrelated.git")
    report = m.audit(root, canonical, _REMOTE)
    assert report["ok"] is True
    assert len(report["clones"]) == 1
