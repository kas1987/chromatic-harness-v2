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


def _write_usage(path, rows):
    import json

    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def test_evidence_proven_learning_floats_up(tmp_path):
    """A low-frontmatter learning with many applied_success should outrank a high-frontmatter unproven one."""
    _write(tmp_path, "proven.md", "2026-05-01", "low", "routing", "Proven routing note")
    _write(
        tmp_path,
        "unproven.md",
        "2026-05-01",
        "high",
        "routing",
        "Unproven routing note",
    )
    usage = tmp_path / "learning_usage.jsonl"
    _write_usage(
        usage,
        [
            {"event_type": "applied_success", "learning_name": "proven"},
            {"event_type": "applied_success", "learning_name": "proven"},
            {"event_type": "applied_success", "learning_name": "proven"},
        ],
    )
    top = sl.select_top(tmp_path, n=2, terms=[], usage_log=usage)
    assert top[0]["title"] == "Proven routing note"


def test_evidence_failure_heavy_learning_deprioritised(tmp_path):
    """A learning with more failures than successes should rank below a plain medium-confidence one."""
    _write(tmp_path, "flaky.md", "2026-05-01", "high", "router", "Flaky high note")
    _write(tmp_path, "plain.md", "2026-05-01", "medium", "router", "Plain medium note")
    usage = tmp_path / "learning_usage.jsonl"
    _write_usage(
        usage,
        [
            {"event_type": "applied_success", "learning_name": "flaky"},
            {"event_type": "applied_success", "learning_name": "flaky"},
            {"event_type": "applied_failure", "learning_name": "flaky"},
            {"event_type": "applied_failure", "learning_name": "flaky"},
            {"event_type": "applied_failure", "learning_name": "flaky"},
        ],
    )
    top = sl.select_top(tmp_path, n=2, terms=[], usage_log=usage)
    assert top[0]["title"] == "Plain medium note"


def test_evidence_load_usage_fail_open(tmp_path):
    """load_usage_evidence returns {} for missing or corrupt files."""
    assert sl.load_usage_evidence(tmp_path / "missing.jsonl") == {}
    corrupt = tmp_path / "corrupt.jsonl"
    corrupt.write_text("not json\n", encoding="utf-8")
    result = sl.load_usage_evidence(corrupt)
    assert isinstance(result, dict)


def test_select_top_no_usage_log_unchanged(tmp_path):
    """select_top without usage_log behaves identically to original (no regression)."""
    _write(tmp_path, "a.md", "2026-05-01", "high", "x", "High note")
    _write(tmp_path, "b.md", "2026-05-01", "low", "y", "Low note")
    top = sl.select_top(tmp_path, n=2)
    assert top[0]["title"] == "High note"
