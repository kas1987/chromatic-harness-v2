"""Tests for command_telemetry.py (dnif / gh-106). Network-free, tmp-isolated."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("command_telemetry", REPO / "scripts" / "command_telemetry.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["command_telemetry"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_log_writes_record(tmp_path):
    m = _mod()
    p = tmp_path / "inv.jsonl"
    rec = m.log_invocation("/go", actor="claude", path=p)
    assert rec["command"] == "/go"
    assert rec["invocation_id"].startswith("inv-")
    assert p.is_file()


def test_known_flag_true_for_registry_command(tmp_path):
    m = _mod()
    p = tmp_path / "inv.jsonl"
    # real registry on the branch contains /go
    rec = m.log_invocation("/go", path=p)
    assert rec["known"] is True


def test_unknown_command_recorded_not_rejected(tmp_path):
    m = _mod()
    p = tmp_path / "inv.jsonl"
    rec = m.log_invocation("/not-a-command", path=p)
    assert rec["known"] is False
    assert len(m.load_invocations(p)) == 1  # still recorded


def test_query_by_command(tmp_path):
    m = _mod()
    p = tmp_path / "inv.jsonl"
    m.log_invocation("/go", path=p)
    m.log_invocation("/ship", path=p)
    m.log_invocation("/go", path=p)
    assert len(m.query(p, command="/go")) == 2


def test_query_by_actor_and_status(tmp_path):
    m = _mod()
    p = tmp_path / "inv.jsonl"
    m.log_invocation("/go", actor="alice", status="completed", path=p)
    m.log_invocation("/go", actor="bob", status="failed", path=p)
    assert len(m.query(p, actor="alice")) == 1
    assert len(m.query(p, status="failed")) == 1


def test_invalid_status_coerced(tmp_path):
    m = _mod()
    p = tmp_path / "inv.jsonl"
    rec = m.log_invocation("/go", status="bogus", path=p)
    assert rec["status"] == "completed"


def test_load_tolerates_corrupt_line(tmp_path):
    m = _mod()
    p = tmp_path / "inv.jsonl"
    m.log_invocation("/go", path=p)
    with p.open("a", encoding="utf-8") as fh:
        fh.write("{ not json\n")
    assert len(m.load_invocations(p)) == 1


def test_summarize_rolls_up(tmp_path):
    m = _mod()
    p = tmp_path / "inv.jsonl"
    m.log_invocation("/go", mutated=True, path=p)
    m.log_invocation("/go", path=p)
    m.log_invocation("/ship", mutated=True, path=p)
    out = m.summarize(p)
    assert out["invocation_count"] == 3
    assert out["mutating_count"] == 2
    assert out["by_command"]["/go"] == 2


def test_known_commands_reads_real_registry():
    m = _mod()
    names = m.known_commands()
    assert "/go" in names and "/recover" in names


def test_summarize_artifact_written_beside_log_not_production(tmp_path):
    """Artifact must be written beside the log file, not to the production directory."""
    m = _mod()
    p = tmp_path / "inv.jsonl"
    m.log_invocation("/go", path=p)
    m.summarize(p)
    expected = tmp_path / "latest.json"
    assert expected.is_file(), "artifact should be written beside the log file, not the production directory"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
