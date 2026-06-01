"""Tests for KOS Stage 8 feedback loop — learnings → candidates.

Verifies high-confidence learnings are staged as pending candidates, that
already-represented sources are skipped (idempotency), and that the
feedback_loop_pct KPI counts learning-sourced candidates.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "scripts"


def _load(mod_name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(mod_name, _SCRIPTS / rel_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _write_learning(d: Path, slug: str, *, confidence: str, tags: str = "[routing]") -> None:
    (d / f"{slug}.md").write_text(
        f"---\nid: learning-{slug}\ntype: learning\nconfidence: {confidence}\n"
        f"category: process\ntags: {tags}\n---\n\n# Learning: {slug.replace('-', ' ')}\n\nbody\n",
        encoding="utf-8",
    )


def _patch_dirs(fb, learnings: Path, candidates: Path) -> None:
    fb.LEARNINGS_DIR = learnings
    fb.CANDIDATES_DIR = candidates


def test_stages_high_confidence_learnings(tmp_path, monkeypatch):
    fb = _load("feedback_loop", "feedback_loop.py")
    learnings = tmp_path / "learnings"
    candidates = tmp_path / "candidates"
    learnings.mkdir()
    candidates.mkdir()
    _write_learning(learnings, "high-conf-one", confidence="high")  # 0.9
    _write_learning(learnings, "explicit-085", confidence="0.85")
    _write_learning(learnings, "low-conf", confidence="low")  # 0.3 — excluded
    _patch_dirs(fb, learnings, candidates)

    summary = fb.run_feedback_loop(min_confidence=0.8, dry_run=False)

    assert summary["status"] == "ok"
    assert summary["staged"] == 2
    assert summary["below_threshold"] == 1
    staged_files = sorted(p.name for p in candidates.glob("*.md"))
    assert staged_files == ["explicit-085.md", "high-conf-one.md"]


def test_staged_candidate_has_pending_status_and_learning_source(tmp_path):
    fb = _load("feedback_loop", "feedback_loop.py")
    learnings = tmp_path / "learnings"
    candidates = tmp_path / "candidates"
    learnings.mkdir()
    candidates.mkdir()
    _write_learning(learnings, "flywheel-insight", confidence="0.9")
    _patch_dirs(fb, learnings, candidates)

    fb.run_feedback_loop(min_confidence=0.8, dry_run=False)
    text = (candidates / "flywheel-insight.md").read_text(encoding="utf-8")
    assert "status: pending" in text
    assert "source_type: learning" in text
    assert "canon_map: routing" in text  # inferred from [routing] tag


def test_idempotent_skips_existing_source(tmp_path):
    fb = _load("feedback_loop", "feedback_loop.py")
    learnings = tmp_path / "learnings"
    candidates = tmp_path / "candidates"
    learnings.mkdir()
    candidates.mkdir()
    _write_learning(learnings, "repeat-me", confidence="0.9")
    _patch_dirs(fb, learnings, candidates)

    first = fb.run_feedback_loop(min_confidence=0.8, dry_run=False)
    assert first["staged"] == 1
    second = fb.run_feedback_loop(min_confidence=0.8, dry_run=False)
    assert second["staged"] == 0
    assert second["already_staged"] >= 1


def test_dry_run_writes_nothing(tmp_path):
    fb = _load("feedback_loop", "feedback_loop.py")
    learnings = tmp_path / "learnings"
    candidates = tmp_path / "candidates"
    learnings.mkdir()
    candidates.mkdir()
    _write_learning(learnings, "ghost", confidence="0.9")
    _patch_dirs(fb, learnings, candidates)

    summary = fb.run_feedback_loop(min_confidence=0.8, dry_run=True)
    assert summary["staged"] == 1
    assert list(candidates.glob("*.md")) == []


def test_missing_learnings_dir_skips(tmp_path):
    fb = _load("feedback_loop", "feedback_loop.py")
    _patch_dirs(fb, tmp_path / "nonexistent", tmp_path / "candidates")
    summary = fb.run_feedback_loop(min_confidence=0.8, dry_run=False)
    assert summary["status"] == "skipped"
    assert summary["staged"] == 0


def test_feedback_loop_pct_collector(tmp_path):
    collector = _load("feedback_loop_pct", "kpi_collectors/feedback_loop_pct.py")
    candidates = tmp_path / "candidates"
    candidates.mkdir()
    (candidates / "from-learning.md").write_text(
        "---\nname: a\nsource_type: learning\nstatus: pending\n---\nx\n",
        encoding="utf-8",
    )
    (candidates / "from-pattern.md").write_text(
        "---\nname: b\nsource_type: pattern\nstatus: pending\n---\nx\n",
        encoding="utf-8",
    )
    collector.CANDIDATES_DIR = candidates

    import io
    import json
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        collector.main()
    result = json.loads(buf.getvalue())
    assert result["total_candidates"] == 2
    assert result["learning_candidates"] == 1
    assert result["feedback_loop_pct"] == 50.0
