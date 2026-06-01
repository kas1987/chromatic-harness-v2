"""OBS-002: file claim/release collision control. Hermetic, subprocess-based.

Exercises the four acceptance checks against a throwaway repo root:
  1. first writer can claim files
  2. a second writer (different session) claiming the same file exits non-zero
  3. the blocked claim is logged + routed to COLLISION_REGISTER.md
  4. release clears active-writer entries
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLAIM = REPO / "scripts" / "claim_files.py"
RELEASE = REPO / "scripts" / "release_files.py"


def _root(tmp_path: Path) -> Path:
    (tmp_path / ".chromatic").mkdir(parents=True, exist_ok=True)
    (tmp_path / "00_META" / "observability").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _claim(root: Path, writer: str, session: str, *files: str, force: bool = False):
    args = [
        sys.executable,
        str(CLAIM),
        "--repo-root",
        str(root),
        "--writer",
        writer,
        "--session",
        session,
        "--files",
        *files,
    ]
    if force:
        args.append("--force")
    return subprocess.run(args, capture_output=True, text=True, timeout=60)


def _release(root: Path, session: str, all_for_session: bool = True):
    args = [sys.executable, str(RELEASE), "--repo-root", str(root), "--session", session]
    if all_for_session:
        args.append("--all-for-session")
    return subprocess.run(args, capture_output=True, text=True, timeout=60)


def _claims(root: Path) -> dict:
    p = root / ".chromatic" / "active_writers.json"
    return json.loads(p.read_text(encoding="utf-8")).get("claims", {}) if p.is_file() else {}


def test_first_writer_can_claim(tmp_path):
    root = _root(tmp_path)
    r = _claim(root, "alice", "sess-A", "src/foo.py")
    assert r.returncode == 0, r.stderr
    assert any(k.endswith("foo.py") for k in _claims(root))


def test_second_writer_same_file_is_blocked(tmp_path):
    root = _root(tmp_path)
    assert _claim(root, "alice", "sess-A", "src/foo.py").returncode == 0
    blocked = _claim(root, "bob", "sess-B", "src/foo.py")
    assert blocked.returncode == 3, f"expected exit 3, got {blocked.returncode}: {blocked.stderr}"


def test_collision_is_logged_and_routed_to_register(tmp_path):
    root = _root(tmp_path)
    _claim(root, "alice", "sess-A", "src/foo.py")
    _claim(root, "bob", "sess-B", "src/foo.py")
    register = (root / "00_META" / "observability" / "COLLISION_REGISTER.md").read_text(encoding="utf-8")
    assert "COLLISION-" in register and "foo.py" in register
    log = root / "00_META" / "observability" / "COLLISION_LOG.jsonl"
    assert log.is_file()
    rec = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert rec["incoming_writer"] == "bob" and any("foo.py" in f for f in rec["files"])


def test_same_session_reclaim_not_blocked(tmp_path):
    root = _root(tmp_path)
    assert _claim(root, "alice", "sess-A", "src/foo.py").returncode == 0
    assert _claim(root, "alice", "sess-A", "src/foo.py").returncode == 0


def test_release_clears_entries(tmp_path):
    root = _root(tmp_path)
    _claim(root, "alice", "sess-A", "src/foo.py", "src/bar.py")
    assert len(_claims(root)) == 2
    r = _release(root, "sess-A", all_for_session=True)
    assert r.returncode == 0, r.stderr
    assert _claims(root) == {}


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
