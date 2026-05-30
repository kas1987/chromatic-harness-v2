"""Tests for session lifecycle telemetry (telemetry P0 bead).

Verifies brand-new sessions emit a session.boot event to the two-log audit
spine immediately, that cold-start is recorded, and that emission is fail-open.

Run with: pytest tests/test_session_events.py -v
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

_RUNTIME = Path(__file__).resolve().parents[1] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))


def _load(name: str):
    # Import as a real package so `from .two_log import ...` resolves.
    return importlib.import_module(f"audit.{name}")


@pytest.fixture
def repo(tmp_path):
    # A minimal repo root the TwoLogAudit will write under.
    (tmp_path / "00_SOURCE_OF_TRUTH").mkdir()
    return tmp_path


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_boot_emits_to_execution_and_trace(repo, monkeypatch):
    monkeypatch.setenv("CHROMATIC_SESSION_ID", "sess-cold-123")
    se = _load("session_events")
    res = se.emit_session_boot(repo, cold_start=True, invoked_by="claude")
    assert res["ok"] is True
    assert res["session_id"] == "sess-cold-123"

    exec_log = repo / "07_LOGS_AND_AUDIT" / "execution" / "execution.jsonl"
    trace_log = repo / "07_LOGS_AND_AUDIT" / "traces" / "traces.jsonl"
    assert exec_log.is_file() and trace_log.is_file()

    rows = _read_jsonl(exec_log)
    assert rows[-1]["event_type"] == "session.boot"
    assert rows[-1]["cold_start"] is True
    assert rows[-1]["session_id"] == "sess-cold-123"
    assert "boot_ts" in rows[-1]

    spans = _read_jsonl(trace_log)
    assert spans[-1]["name"] == "session.boot"
    assert spans[-1]["attributes"]["session.cold_start"] is True


def test_warm_start_records_cold_start_false(repo):
    se = _load("session_events")
    se.emit_session_boot(repo, cold_start=False)
    rows = _read_jsonl(repo / "07_LOGS_AND_AUDIT" / "execution" / "execution.jsonl")
    assert rows[-1]["cold_start"] is False


def test_end_event_emitted(repo):
    se = _load("session_events")
    res = se.emit_session_end(repo, invoked_by="claude_code")
    assert res["ok"] is True
    rows = _read_jsonl(repo / "07_LOGS_AND_AUDIT" / "execution" / "execution.jsonl")
    assert rows[-1]["event_type"] == "session.end"
    assert rows[-1]["invoked_by"] == "claude_code"


def test_emission_is_fail_open():
    se = _load("session_events")

    class Boom:
        def append_execution(self, *_a, **_k):
            raise RuntimeError("disk full")

    res = se.emit_session_boot(Path("/nonexistent"), audit=Boom())
    assert res["ok"] is False
    assert "disk full" in res["error"]
