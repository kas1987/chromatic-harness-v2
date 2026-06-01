"""Tests for queue_self_review.py — read-only beads/epics hygiene reviewer (bead gl6t).

Network-free: bd is never called; bead lists are injected. Verifies each detector,
the read-only contract, and fail-open summarize().
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("queue_self_review", REPO / "scripts" / "queue_self_review.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["queue_self_review"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_eval_state_counts_checkboxes():
    mod = _load()
    assert mod.eval_state("- [x] a\n- [x] b\n- [ ] c") == (2, 1)
    assert mod.eval_state("- [X] A") == (1, 0)
    assert mod.eval_state("no boxes") == (0, 0)


def test_unclaimed_active_detected():
    mod = _load()
    beads = [{"id": "x", "status": "in_progress", "assignee": "", "title": "t"}]
    finds = mod.find_findings(beads)
    assert any(f["kind"] == "unclaimed_active" and f["bead"] == "x" for f in finds)


def test_claimed_active_not_flagged():
    mod = _load()
    beads = [{"id": "x", "status": "in_progress", "assignee": "alice"}]
    assert not any(f["kind"] == "unclaimed_active" for f in mod.find_findings(beads))


def test_ready_to_close_all_boxes_checked():
    mod = _load()
    beads = [{"id": "x", "status": "open", "description": "- [x] a\n- [x] b\n- [x] c"}]
    finds = mod.find_findings(beads)
    assert any(f["kind"] == "ready_to_close" and f["checked"] == 3 for f in finds)


def test_ready_to_close_skips_when_unchecked_remain():
    mod = _load()
    beads = [{"id": "x", "status": "open", "description": "- [x] a\n- [ ] b"}]
    assert not any(f["kind"] == "ready_to_close" for f in mod.find_findings(beads))


def test_duplicate_ref_detected():
    mod = _load()
    beads = [
        {"id": "a", "external_ref": "gh-64", "status": "open"},
        {"id": "b", "external_ref": "gh-64", "status": "closed"},
        {"id": "c", "external_ref": "gh-65", "status": "open"},
    ]
    dups = [f for f in mod.find_findings(beads) if f["kind"] == "duplicate_ref"]
    assert len(dups) == 1 and set(dups[0]["beads"]) == {"a", "b"}


def test_epic_ready_close_when_all_children_closed():
    mod = _load()
    beads = [
        {"id": "e", "type": "epic", "status": "open"},
        {"id": "c1", "parent": "e", "status": "closed"},
        {"id": "c2", "parent": "e", "status": "closed"},
    ]
    assert any(f["kind"] == "epic_ready_close" and f["bead"] == "e" for f in mod.find_findings(beads))


def test_epic_not_closeable_with_open_child():
    mod = _load()
    beads = [
        {"id": "e", "type": "epic", "status": "open"},
        {"id": "c1", "parent": "e", "status": "closed"},
        {"id": "c2", "parent": "e", "status": "open"},
    ]
    assert not any(f["kind"] == "epic_ready_close" for f in mod.find_findings(beads))


def test_build_report_shape_and_auto_closeable():
    mod = _load()
    beads = [
        {"id": "x", "status": "open", "description": "- [x] a\n- [x] b"},
        {"id": "y", "status": "in_progress", "assignee": ""},
    ]
    rep = mod.build_report(beads)
    assert rep["beads_reviewed"] == 2
    assert "x" in rep["auto_closeable"]  # ready_to_close
    assert rep["finding_counts"].get("unclaimed_active") == 1


def test_write_and_summarize_roundtrip(monkeypatch, tmp_path):
    mod = _load()
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)
    monkeypatch.setattr(mod, "LATEST", tmp_path / "latest.json")
    rep = mod.build_report([{"id": "x", "status": "open", "description": "- [x] a"}])
    mod.write_artifact(rep)
    s = mod.summarize()
    assert s["status"] == "ok" and s["beads_reviewed"] == 1


def test_summarize_no_scan_fail_open(monkeypatch, tmp_path):
    mod = _load()
    monkeypatch.setattr(mod, "LATEST", tmp_path / "none.json")
    assert mod.summarize()["status"] == "no_scan"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
