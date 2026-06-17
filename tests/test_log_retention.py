"""Tests for scripts/log_retention.py (shared exhaust-pruning helper)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from log_retention import prune_dir, rotate_jsonl  # noqa: E402


def test_rotate_jsonl_caps_lines(tmp_path: Path):
    f = tmp_path / "history.jsonl"
    f.write_text("".join(f'{{"i":{i}}}\n' for i in range(100)), encoding="utf-8")
    # dry-run reports but does not modify
    kept, dropped, freed = rotate_jsonl(f, max_lines=10, apply=False)
    assert (kept, dropped) == (10, 90) and freed > 0
    assert len(f.read_text(encoding="utf-8").splitlines()) == 100
    # apply trims to newest 10 (tail preserved)
    kept, dropped, freed = rotate_jsonl(f, max_lines=10, apply=True)
    lines = f.read_text(encoding="utf-8").splitlines()
    assert kept == 10 and dropped == 90
    assert lines[0] == '{"i":90}' and lines[-1] == '{"i":99}'


def test_rotate_jsonl_noop_when_small(tmp_path: Path):
    f = tmp_path / "history.jsonl"
    f.write_text('{"a":1}\n{"a":2}\n', encoding="utf-8")
    assert rotate_jsonl(f, max_lines=10, apply=True) == (2, 0, 0)


def test_rotate_jsonl_archives(tmp_path: Path):
    f = tmp_path / "history.jsonl"
    f.write_text("".join(f"line{i}\n" for i in range(20)), encoding="utf-8")
    adir = tmp_path / "arch"
    rotate_jsonl(f, max_lines=5, apply=True, archive_dir=adir)
    archived = (adir / "history.jsonl.rotated").read_text(encoding="utf-8").splitlines()
    assert archived[0] == "line0" and len(archived) == 15


def test_rotate_jsonl_missing_file(tmp_path: Path):
    assert rotate_jsonl(tmp_path / "nope.jsonl", apply=True) == (0, 0, 0)


def _make(p: Path, age_days: float):
    p.write_text("x", encoding="utf-8")
    t = time.time() - age_days * 86400
    import os

    os.utime(p, (t, t))


def test_keeps_newest_n_and_protects(tmp_path: Path):
    for i in range(10):
        _make(tmp_path / f"run_{i}.json", age_days=i)  # run_0 newest
    (tmp_path / "latest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "history.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("# keep", encoding="utf-8")

    kept, removed, _ = prune_dir(tmp_path, keep=3, apply=True)
    names = sorted(p.name for p in tmp_path.iterdir())

    assert "latest.json" in names and "history.jsonl" in names and "notes.md" in names
    assert removed == 7
    # 3 newest run_* survive
    assert {"run_0.json", "run_1.json", "run_2.json"}.issubset(set(names))
    assert "run_9.json" not in names


def test_dry_run_deletes_nothing(tmp_path: Path):
    for i in range(5):
        _make(tmp_path / f"run_{i}.json", age_days=i)
    before = sorted(p.name for p in tmp_path.iterdir())
    kept, would_remove, _ = prune_dir(tmp_path, keep=2, apply=False)
    after = sorted(p.name for p in tmp_path.iterdir())
    assert before == after  # nothing deleted in dry-run
    assert would_remove == 3


def test_keep_days_filter(tmp_path: Path):
    _make(tmp_path / "recent.json", age_days=1)
    _make(tmp_path / "old.json", age_days=40)
    # keep is generous (both within count) but keep_days drops the 40d file
    kept, removed, _ = prune_dir(tmp_path, keep=50, keep_days=30, apply=True)
    names = [p.name for p in tmp_path.iterdir()]
    assert "recent.json" in names and "old.json" not in names


def test_fail_open_on_missing_dir(tmp_path: Path):
    assert prune_dir(tmp_path / "does_not_exist", apply=True) == (0, 0, 0)


def test_archive_then_delete(tmp_path: Path):
    arc = tmp_path / "arc"
    src = tmp_path / "src"
    src.mkdir()
    for i in range(4):
        _make(src / f"run_{i}.json", age_days=i)
    prune_dir(src, keep=1, apply=True, archive_dir=arc)
    tarballs = list(arc.glob("*.tar.gz"))
    assert tarballs and tarballs[0].stat().st_size > 0
    assert len(list(src.glob("run_*.json"))) == 1
