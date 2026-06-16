"""Tests for scripts/log_retention.py (shared exhaust-pruning helper)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from log_retention import prune_dir  # noqa: E402


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
