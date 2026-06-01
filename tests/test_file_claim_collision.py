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


# --- regressions from code-review feedback (Codex/Gemini on PR #143) ---


def test_release_normalizes_dotslash_paths(tmp_path):
    """Gemini HIGH: release must canonicalize paths like claim does, so a
    `./src/foo.py` release matches the stored `src/foo.py` claim."""
    root = _root(tmp_path)
    _claim(root, "alice", "sess-A", "src/foo.py")
    r = subprocess.run(
        [sys.executable, str(RELEASE), "--repo-root", str(root), "--session", "sess-A", "--files", "./src/foo.py"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    assert _claims(root) == {}, "dotslash release should have cleared the normalized claim"


def test_collision_routed_even_when_register_dir_absent(tmp_path):
    """Codex P2: routing must create 00_META/observability before writing the
    register, so a blocked claim is still logged when the dir doesn't pre-exist."""
    root = tmp_path
    (root / ".chromatic").mkdir(parents=True, exist_ok=True)  # NO 00_META/observability
    _claim(root, "alice", "sess-A", "src/foo.py")
    blocked = _claim(root, "bob", "sess-B", "src/foo.py")
    assert blocked.returncode == 3
    register = root / "00_META" / "observability" / "COLLISION_REGISTER.md"
    assert register.is_file() and "foo.py" in register.read_text(encoding="utf-8")


def test_detect_collisions_handles_non_object_json(tmp_path):
    """Gemini/Copilot HIGH: detector must not crash on a valid-but-non-object
    active-writers file (e.g. a JSON list)."""
    root = _root(tmp_path)
    (root / ".chromatic" / "active_writers.json").write_text("[]", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "detect_file_collisions.py"), "--repo-root", str(root)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 2, f"expected graceful exit 2, got {r.returncode}: {r.stderr}"
    assert "malformed" in r.stderr.lower()


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
