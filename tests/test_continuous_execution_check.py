"""Tests for the Continuous Execution & Bead Review SOP checker.

Run with: pytest tests/test_continuous_execution_check.py -v
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "continuous_execution_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("continuous_execution_check", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_detects_swot_seed_noise_cluster():
    mod = _load()
    items = [
        {
            "id": "a",
            "priority": 2,
            "title": f"Generate next EPIC-SWOT [{i}] before final closeout",
        }
        for i in range(14)
    ] + [{"id": "real", "priority": 0, "title": "Fix telemetry cold-start gap"}]
    report = mod.analyze(items)
    assert report["ready_count"] == 15
    assert report["noise_clusters"].get("epic_swot_seed") == 14
    # actionable list excludes the noise
    assert any(t["id"] == "real" for t in report["top_actionable"])
    assert all("EPIC-SWOT" not in t["title"] for t in report["top_actionable"])


def test_clean_queue_has_no_noise():
    mod = _load()
    items = [
        {"id": "a", "priority": 1, "title": "Wire router span emission"},
        {"id": "b", "priority": 2, "title": "Add KPI console"},
    ]
    report = mod.analyze(items)
    assert report["noise_clusters"] == {}
    assert report["noise_total"] == 0
    assert len(report["top_actionable"]) == 2


def test_priority_histogram():
    mod = _load()
    items = [
        {"id": "a", "priority": 0, "title": "x"},
        {"id": "b", "priority": 1, "title": "y"},
        {"id": "c", "priority": 1, "title": "z"},
    ]
    report = mod.analyze(items)
    assert report["by_priority"] == {"0": 1, "1": 2}


def test_extract_json_tolerates_preamble():
    mod = _load()
    assert mod._extract_json('LOG line\n[{"id": "x"}]') == [{"id": "x"}]
    assert mod._extract_json('[{"id": "y"}]') == [{"id": "y"}]
    assert mod._extract_json("not json at all") is None
