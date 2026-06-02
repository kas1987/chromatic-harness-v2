"""OBS-006: git-state snapshots + last-known-good flow.

Hermetic — each test builds a real throwaway git repo in tmp_path and runs the
scripts as subprocesses against it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"


def _clean_env() -> dict[str, str]:
    """Environment with inherited GIT_* location vars stripped.

    The pre-push hook exports GIT_DIR (and friends) pointing at the live repo.
    Without this, `git` run with cwd=tmp_path would still operate on the live
    repo, so this 'hermetic' fixture would commit a.txt onto the active branch.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(root), env=_clean_env(), check=True, capture_output=True, text=True)


def _init_repo(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "a.txt").write_text("hello\n", encoding="utf-8")
    _git(root, "add", "a.txt")
    _git(root, "commit", "-q", "-m", "init")


def _run(script: str, root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), "--repo-root", str(root), *extra],
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_snapshot_outputs_branch_commit_dirty_and_changed_files(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "b.txt").write_text("new\n", encoding="utf-8")  # untracked
    (tmp_path / "a.txt").write_text("changed\n", encoding="utf-8")  # modified
    r = _run("snapshot_git_state.py", tmp_path)
    assert r.returncode == 0
    snap = json.loads((tmp_path / ".chromatic" / "last_known_good.json").read_text(encoding="utf-8"))
    assert snap["git"]["branch"] not in (None, "")
    assert snap["git"]["commit"] not in (None, "unknown", "")
    assert snap["git"]["dirty"] is True
    cf = snap["changed_files"]
    assert "b.txt" in cf["untracked"]
    assert "a.txt" in cf["modified"]


def test_snapshot_classifies_staged_files(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "c.txt").write_text("staged\n", encoding="utf-8")
    _git(tmp_path, "add", "c.txt")
    _run("snapshot_git_state.py", tmp_path)
    snap = json.loads((tmp_path / ".chromatic" / "last_known_good.json").read_text(encoding="utf-8"))
    assert "c.txt" in snap["changed_files"]["staged"]


def test_snapshot_writes_latest_pointer_for_incident_linking(tmp_path):
    _init_repo(tmp_path)
    _run("snapshot_git_state.py", tmp_path)
    latest = tmp_path / ".chromatic" / "latest_snapshot.json"
    assert latest.is_file()
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert "snapshot_path" in data


def test_check_dirty_advisory_exits_zero_when_dirty(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("dirty\n", encoding="utf-8")
    r = _run("check_dirty_state.py", tmp_path)
    assert r.returncode == 0
    assert "Dirty working tree" in r.stdout


def test_check_dirty_strict_exits_nonzero_when_dirty(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("dirty\n", encoding="utf-8")
    r = _run("check_dirty_state.py", tmp_path, "--strict")
    assert r.returncode == 1


def test_check_dirty_strict_exits_zero_when_clean(tmp_path):
    _init_repo(tmp_path)
    r = _run("check_dirty_state.py", tmp_path, "--strict")
    assert r.returncode == 0
    assert "clean" in r.stdout.lower()


def test_lkg_records_when_clean(tmp_path):
    _init_repo(tmp_path)
    r = _run("update_last_known_good.py", tmp_path)
    assert r.returncode == 0
    cp = json.loads((tmp_path / ".chromatic" / "last_known_good.json").read_text(encoding="utf-8"))
    assert cp["checkpoint"] == "last_known_good"
    assert cp["validated"] is True


def test_lkg_refuses_when_dirty(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("dirty\n", encoding="utf-8")
    r = _run("update_last_known_good.py", tmp_path)
    assert r.returncode == 1
    assert "dirty" in r.stderr.lower()


def test_lkg_force_records_dirty_with_validated_false(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("dirty\n", encoding="utf-8")
    r = _run("update_last_known_good.py", tmp_path, "--force")
    assert r.returncode == 0
    cp = json.loads((tmp_path / ".chromatic" / "last_known_good.json").read_text(encoding="utf-8"))
    assert cp["validated"] is False
    assert cp["forced"] is True


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
