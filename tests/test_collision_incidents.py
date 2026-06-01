"""Tests for collision_incidents.py (P1-CC-009 / ju0o.8). Network-free, tmp-isolated."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("collision_incidents", REPO / "scripts" / "collision_incidents.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["collision_incidents"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_record_writes_incident(tmp_path):
    ci = _load()
    p = tmp_path / "incidents.jsonl"
    rec = ci.record_incident("blocked_write", "AgentB", "scripts/foo.py", "held by AgentA", path=p)
    assert rec["type"] == "blocked_write"
    assert rec["incident_id"].startswith("inc-")
    assert p.is_file()


def test_incident_is_queryable(tmp_path):
    ci = _load()
    p = tmp_path / "incidents.jsonl"
    ci.record_incident("blocked_write", "AgentB", "scripts/foo.py", path=p)
    ci.record_incident("denied_claim", "AgentC", "queue:bead-1", path=p)
    rows = ci.query_incidents(p, incident_type="blocked_write")
    assert len(rows) == 1
    assert rows[0]["agent"] == "AgentB"


def test_query_by_agent(tmp_path):
    ci = _load()
    p = tmp_path / "incidents.jsonl"
    ci.record_incident("blocked_write", "AgentB", path=p)
    ci.record_incident("deadlock", "AgentB", path=p)
    ci.record_incident("denied_claim", "AgentC", path=p)
    assert len(ci.query_incidents(p, agent="AgentB")) == 2


def test_unknown_type_coerced_to_other(tmp_path):
    ci = _load()
    p = tmp_path / "incidents.jsonl"
    rec = ci.record_incident("bogus_type", "AgentX", path=p)
    assert rec["type"] == "other"


def test_load_tolerates_corrupt_line(tmp_path):
    ci = _load()
    p = tmp_path / "incidents.jsonl"
    ci.record_incident("blocked_write", "AgentB", path=p)
    with p.open("a", encoding="utf-8") as fh:
        fh.write("{ this is not json\n")
    rows = ci.load_incidents(p)
    assert len(rows) == 1  # corrupt line skipped


def test_summarize_rolls_up_by_type(tmp_path):
    ci = _load()
    p = tmp_path / "incidents.jsonl"
    ci.record_incident("blocked_write", "AgentB", path=p)
    ci.record_incident("blocked_write", "AgentC", path=p)
    ci.record_incident("deadlock", "AgentD", path=p)
    out = ci.summarize(p)
    assert out["incident_count"] == 3
    assert out["by_type"]["blocked_write"] == 2
    assert out["by_type"]["deadlock"] == 1


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
