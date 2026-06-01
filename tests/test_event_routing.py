"""OBS-004: route_event.py routes events to incident/collision/queue artifacts.

Hermetic, subprocess-based against a throwaway repo root.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROUTER = REPO / "scripts" / "route_event.py"


def _seed(root: Path, *events: dict) -> None:
    log = root / "00_META" / "observability" / "ERROR_LOG.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    (root / "00_META" / "queues").mkdir(parents=True, exist_ok=True)
    log.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _route(root: Path, event_id: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROUTER), "--repo-root", str(root), "--event-id", event_id],
        capture_output=True, text=True, timeout=60,
    )


def _read(root: Path, rel: str) -> str:
    p = root / rel
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _ev(eid, **over) -> dict:
    e = {"event_id": eid, "severity": "info", "category": "manual_note",
         "status": "open", "source": {"surface": "ci"}, "raw_excerpt": "x"}
    e.update(over)
    return e


def test_critical_event_appends_to_incident_log(tmp_path):
    _seed(tmp_path, _ev("evt-crit", severity="critical", category="tool_failure"))
    assert _route(tmp_path, "evt-crit").returncode == 0
    inc = _read(tmp_path, "00_META/observability/INCIDENT_LOG.md")
    assert "evt-crit" in inc


def test_file_collision_event_appends_to_register(tmp_path):
    _seed(tmp_path, _ev("evt-coll", severity="high", category="file_collision",
                        files_touched=["src/a.py"]))
    assert _route(tmp_path, "evt-coll").returncode == 0
    reg = _read(tmp_path, "00_META/observability/COLLISION_REGISTER.md")
    assert "evt-coll" in reg and "src/a.py" in reg


def test_unresolved_high_error_creates_queue_entry(tmp_path):
    _seed(tmp_path, _ev("evt-q", severity="high", category="test_failure", status="open"))
    assert _route(tmp_path, "evt-q").returncode == 0
    q = _read(tmp_path, "00_META/queues/ERROR_REMEDIATION_QUEUE.md")
    assert "evt-q" in q


def test_resolved_error_is_not_queued(tmp_path):
    _seed(tmp_path, _ev("evt-done", severity="high", category="test_failure", status="resolved"))
    assert _route(tmp_path, "evt-done").returncode == 0
    q = _read(tmp_path, "00_META/queues/ERROR_REMEDIATION_QUEUE.md")
    assert "evt-done" not in q


def test_downstream_records_link_source_event_id(tmp_path):
    _seed(tmp_path, _ev("evt-link", severity="critical", category="file_collision",
                        files_touched=["x"]))
    _route(tmp_path, "evt-link")
    assert "evt-link" in _read(tmp_path, "00_META/observability/INCIDENT_LOG.md")
    assert "evt-link" in _read(tmp_path, "00_META/observability/COLLISION_REGISTER.md")
    assert "evt-link" in _read(tmp_path, "00_META/queues/ERROR_REMEDIATION_QUEUE.md")


def test_malformed_log_line_does_not_crash_routing(tmp_path):
    log = tmp_path / "00_META" / "observability" / "ERROR_LOG.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "00_META" / "queues").mkdir(parents=True, exist_ok=True)
    log.write_text('{ broken json\n' + json.dumps(_ev("evt-ok", severity="critical")) + "\n",
                   encoding="utf-8")
    r = _route(tmp_path, "evt-ok")
    assert r.returncode == 0, r.stderr
    assert "evt-ok" in _read(tmp_path, "00_META/observability/INCIDENT_LOG.md")


def test_missing_event_exits_2(tmp_path):
    _seed(tmp_path, _ev("evt-a"))
    assert _route(tmp_path, "evt-missing").returncode == 2


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
