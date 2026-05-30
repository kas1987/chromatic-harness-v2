"""Tests for session-start learning selection (bead chromatic-harness-v2-yl2a).

Run with: pytest tests/test_select_learnings.py -v
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[1] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

sl = importlib.import_module("knowledge.select_learnings")


def _write(d: Path, name: str, date: str, conf: str, tags: str, title: str) -> None:
    (d / name).write_text(
        f"---\ndate: {date}\nconfidence: {conf}\ntags: [{tags}]\n---\n\n# {title}\n\nbody\n",
        encoding="utf-8",
    )


def test_parse_and_load(tmp_path):
    _write(tmp_path, "a.md", "2026-05-01", "high", "routing, cost", "Routing learning")
    items = sl.load_learnings(tmp_path)
    assert len(items) == 1
    assert items[0]["confidence"] == "high"
    assert items[0]["tags"] == ["routing", "cost"]
    assert items[0]["title"] == "Routing learning"


def test_term_relevance_ranks_first(tmp_path):
    _write(tmp_path, "a.md", "2026-05-01", "low", "telemetry", "Telemetry note")
    _write(tmp_path, "b.md", "2026-05-01", "low", "routing, loop", "Loop guard note")
    top = sl.select_top(tmp_path, n=1, terms=["loop"])
    assert top[0]["title"] == "Loop guard note"


def test_confidence_then_recency_without_terms(tmp_path):
    _write(tmp_path, "a.md", "2026-05-01", "low", "x", "Low old")
    _write(tmp_path, "b.md", "2026-05-09", "high", "y", "High new")
    _write(tmp_path, "c.md", "2026-05-10", "low", "z", "Low newest")
    top = sl.select_top(tmp_path, n=3, terms=[])
    assert top[0]["title"] == "High new"  # confidence wins over recency


def test_format_for_injection_handles_empty():
    assert "no prior learnings" in sl.format_for_injection([])


def test_missing_dir_is_fail_open(tmp_path):
    assert sl.load_learnings(tmp_path / "nope") == []
    assert sl.select_top(tmp_path / "nope", n=3) == []
