"""OBS-011: event lifecycle tools (find / append-only status update / report).

Hermetic, subprocess-based against a throwaway repo root.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
LOG_REL = "00_META/observability/ERROR_LOG.jsonl"


def _seed(root: Path, events: list[dict]) -> None:
    log = root / LOG_REL
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _ev(eid, sev="high", status="open") -> dict:
    return {
        "event_id": eid,
        "timestamp": "2026-06-01T01:00:00Z",
        "repo": "demo",
        "workspace": "/tmp/demo",
        "severity": sev,
        "category": "test_failure",
        "status": status,
        "error_signature": "boom",
        "source": {"surface": "ci"},
    }


def _run(script: str, root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), "--repo-root", str(root), *extra],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _lines(root: Path) -> list[dict]:
    return [json.loads(x) for x in (root / LOG_REL).read_text(encoding="utf-8").splitlines() if x.strip()]


# ---- find_event ----------------------------------------------------------


def test_find_event_locates_by_id(tmp_path):
    _seed(tmp_path, [_ev("evt-1"), _ev("evt-2")])
    r = _run("find_event.py", tmp_path, "--event-id", "evt-2")
    assert r.returncode == 0
    assert json.loads(r.stdout)["event_id"] == "evt-2"


def test_find_event_missing_exits_2(tmp_path):
    _seed(tmp_path, [_ev("evt-1")])
    assert _run("find_event.py", tmp_path, "--event-id", "nope").returncode == 2


def test_find_event_tolerates_malformed_line(tmp_path):
    log = tmp_path / LOG_REL
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("{bad\n" + json.dumps(_ev("evt-1")) + "\n", encoding="utf-8")
    assert _run("find_event.py", tmp_path, "--event-id", "evt-1").returncode == 0


# ---- update_event_status (append-only) -----------------------------------


def test_update_status_appends_without_mutating_history(tmp_path):
    _seed(tmp_path, [_ev("evt-1", status="open")])
    before = (tmp_path / LOG_REL).read_text(encoding="utf-8")
    r = _run("update_event_status.py", tmp_path, "--event-id", "evt-1", "--status", "resolved")
    assert r.returncode == 0, r.stderr
    after_lines = _lines(tmp_path)
    # Original line preserved verbatim; a new record appended.
    assert (tmp_path / LOG_REL).read_text(encoding="utf-8").startswith(before.rstrip("\n"))
    assert len(after_lines) == 2
    upd = after_lines[-1]
    assert upd["event_id"] == "evt-1"  # same id -> groupable
    assert upd["event_type"] == "status_update"
    assert upd["status"] == "resolved"
    assert upd["previous_status"] == "open"


def test_update_status_unknown_event_exits_2(tmp_path):
    _seed(tmp_path, [_ev("evt-1")])
    assert _run("update_event_status.py", tmp_path, "--event-id", "x", "--status", "resolved").returncode == 2


def test_update_status_invalid_status_exits_2(tmp_path):
    _seed(tmp_path, [_ev("evt-1")])
    r = _run("update_event_status.py", tmp_path, "--event-id", "evt-1", "--status", "bogus")
    assert r.returncode == 2
    assert "invalid status" in r.stderr


# ---- end-to-end: report reflects appended latest status ------------------


def test_report_reflects_latest_status_after_update(tmp_path):
    _seed(tmp_path, [_ev("evt-1", sev="critical", status="open")])
    _run("update_event_status.py", tmp_path, "--event-id", "evt-1", "--status", "resolved")
    r = _run("generate_observability_report.py", tmp_path)
    assert r.returncode == 0
    report = Path(r.stdout.strip()).read_text(encoding="utf-8")
    # The critical event is resolved -> it must NOT appear under Unresolved.
    unresolved = report.split("## Unresolved High / Critical Events")[1].split("##")[0]
    assert "evt-1" not in unresolved


def test_find_history_shows_all_lifecycle_records(tmp_path):
    _seed(tmp_path, [_ev("evt-1", status="open")])
    _run("update_event_status.py", tmp_path, "--event-id", "evt-1", "--status", "resolved")
    r = _run("find_event.py", tmp_path, "--event-id", "evt-1", "--history")
    assert r.returncode == 0
    records = json.loads(r.stdout)
    assert len(records) == 2
    assert records[-1]["status"] == "resolved"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
