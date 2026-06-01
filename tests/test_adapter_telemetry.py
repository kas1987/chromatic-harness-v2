"""Tests for scripts/adapter_telemetry.py — adapter command telemetry (dnif).

All tests are network-free and file-system-hermetic via tmp_path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "adapter_telemetry.py"


def _load(tmp_path: Path):
    """Load adapter_telemetry fresh, redirecting file paths to tmp_path."""
    sys.modules.pop("adapter_telemetry", None)
    spec = importlib.util.spec_from_file_location("adapter_telemetry", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    # Redirect storage paths to tmp_path
    mod.INVOCATION_LOG = tmp_path / "invocations.jsonl"
    mod.LATEST_JSON = tmp_path / "latest.json"
    return mod


# ---------------------------------------------------------------------------
# log_invocation
# ---------------------------------------------------------------------------


class TestLogInvocation:
    def test_valid_invocation_writes_record(self, tmp_path):
        mod = _load(tmp_path)
        record = mod.log_invocation("/go", "ok", log_path=mod.INVOCATION_LOG)
        assert record["command"] == "/go"
        assert record["outcome"] == "ok"
        assert mod.INVOCATION_LOG.exists()

    def test_record_has_required_fields(self, tmp_path):
        mod = _load(tmp_path)
        record = mod.log_invocation("/audit", "blocked", log_path=mod.INVOCATION_LOG)
        assert "ts" in record
        assert "run_id" in record
        assert record["run_id"].startswith("tel_")
        assert len(record["run_id"]) == 12  # "tel_" + 8 hex

    def test_optional_fields_included_when_provided(self, tmp_path):
        mod = _load(tmp_path)
        record = mod.log_invocation(
            "/ship",
            "ok",
            mode="execute",
            duration_ms=450,
            detail="shipped v1.2",
            log_path=mod.INVOCATION_LOG,
        )
        assert record["mode"] == "execute"
        assert record["duration_ms"] == 450
        assert record["detail"] == "shipped v1.2"

    def test_optional_fields_absent_when_not_provided(self, tmp_path):
        mod = _load(tmp_path)
        record = mod.log_invocation("/status", "ok", log_path=mod.INVOCATION_LOG)
        assert "mode" not in record
        assert "duration_ms" not in record
        assert "detail" not in record

    def test_custom_run_id_respected(self, tmp_path):
        mod = _load(tmp_path)
        record = mod.log_invocation("/recover", "stop_condition", run_id="tel_custom1", log_path=mod.INVOCATION_LOG)
        assert record["run_id"] == "tel_custom1"

    def test_multiple_calls_append_to_log(self, tmp_path):
        mod = _load(tmp_path)
        mod.log_invocation("/go", "ok", log_path=mod.INVOCATION_LOG)
        mod.log_invocation("/audit", "ok", log_path=mod.INVOCATION_LOG)
        mod.log_invocation("/ship", "error", log_path=mod.INVOCATION_LOG)
        lines = mod.INVOCATION_LOG.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3

    def test_invalid_command_raises_value_error(self, tmp_path):
        mod = _load(tmp_path)
        with pytest.raises(ValueError, match="unknown command"):
            mod.log_invocation("/nonexistent", "ok", log_path=mod.INVOCATION_LOG)

    def test_invalid_outcome_raises_value_error(self, tmp_path):
        mod = _load(tmp_path)
        with pytest.raises(ValueError, match="unknown outcome"):
            mod.log_invocation("/go", "partial", log_path=mod.INVOCATION_LOG)

    def test_all_seven_governed_commands_accepted(self, tmp_path):
        mod = _load(tmp_path)
        for cmd in ["/go", "/audit", "/status", "/ship", "/recover", "/queue", "/explain"]:
            record = mod.log_invocation(cmd, "ok", log_path=mod.INVOCATION_LOG)
            assert record["command"] == cmd

    def test_all_valid_outcomes_accepted(self, tmp_path):
        mod = _load(tmp_path)
        for outcome in ["ok", "blocked", "error", "stop_condition"]:
            record = mod.log_invocation("/go", outcome, log_path=mod.INVOCATION_LOG)
            assert record["outcome"] == outcome


# ---------------------------------------------------------------------------
# recent
# ---------------------------------------------------------------------------


class TestRecent:
    def test_empty_log_returns_empty_list(self, tmp_path):
        mod = _load(tmp_path)
        assert mod.recent(log_path=mod.INVOCATION_LOG) == []

    def test_missing_log_returns_empty_list(self, tmp_path):
        mod = _load(tmp_path)
        assert mod.recent(n=5, log_path=tmp_path / "nonexistent.jsonl") == []

    def test_tail_n_returns_last_n(self, tmp_path):
        mod = _load(tmp_path)
        for i in range(5):
            mod.log_invocation("/go", "ok", detail=str(i), log_path=mod.INVOCATION_LOG)
        tail = mod.recent(n=3, log_path=mod.INVOCATION_LOG)
        assert len(tail) == 3
        assert tail[-1]["detail"] == "4"  # newest last

    def test_corrupt_lines_skipped(self, tmp_path):
        mod = _load(tmp_path)
        mod.INVOCATION_LOG.parent.mkdir(parents=True, exist_ok=True)
        mod.INVOCATION_LOG.write_text(
            '{"command":"/go","outcome":"ok","run_id":"tel_a","ts":"t"}\n'
            "NOT_JSON\n"
            '{"command":"/audit","outcome":"ok","run_id":"tel_b","ts":"t"}\n',
            encoding="utf-8",
        )
        records = mod.recent(n=10, log_path=mod.INVOCATION_LOG)
        assert len(records) == 2


# ---------------------------------------------------------------------------
# build_summary + summarize
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_counts_by_command(self, tmp_path):
        mod = _load(tmp_path)
        mod.log_invocation("/go", "ok", log_path=mod.INVOCATION_LOG)
        mod.log_invocation("/go", "error", log_path=mod.INVOCATION_LOG)
        mod.log_invocation("/audit", "ok", log_path=mod.INVOCATION_LOG)
        summary = mod.build_summary(log_path=mod.INVOCATION_LOG, latest_path=mod.LATEST_JSON)
        assert summary["total_invocations"] == 3
        assert summary["by_command"]["/go"] == 2
        assert summary["by_command"]["/audit"] == 1

    def test_summary_counts_by_outcome(self, tmp_path):
        mod = _load(tmp_path)
        mod.log_invocation("/go", "ok", log_path=mod.INVOCATION_LOG)
        mod.log_invocation("/go", "blocked", log_path=mod.INVOCATION_LOG)
        mod.log_invocation("/ship", "error", log_path=mod.INVOCATION_LOG)
        summary = mod.build_summary(log_path=mod.INVOCATION_LOG, latest_path=mod.LATEST_JSON)
        assert summary["by_outcome"]["ok"] == 1
        assert summary["by_outcome"]["blocked"] == 1
        assert summary["by_outcome"]["error"] == 1

    def test_summary_writes_latest_json(self, tmp_path):
        mod = _load(tmp_path)
        mod.log_invocation("/go", "ok", log_path=mod.INVOCATION_LOG)
        mod.build_summary(log_path=mod.INVOCATION_LOG, latest_path=mod.LATEST_JSON)
        data = json.loads(mod.LATEST_JSON.read_text(encoding="utf-8"))
        assert "total_invocations" in data
        assert "by_command" in data

    def test_summarize_one_liner(self, tmp_path):
        mod = _load(tmp_path)
        mod.log_invocation("/go", "ok", log_path=mod.INVOCATION_LOG)
        mod.log_invocation("/ship", "error", log_path=mod.INVOCATION_LOG)
        line = mod.summarize(log_path=mod.INVOCATION_LOG, latest_path=mod.LATEST_JSON)
        assert "adapter_telemetry" in line
        assert "2 invocations" in line
        assert "1 errors" in line

    def test_summarize_fail_open_when_no_log(self, tmp_path):
        mod = _load(tmp_path)
        line = mod.summarize(log_path=tmp_path / "missing.jsonl", latest_path=mod.LATEST_JSON)
        assert "adapter_telemetry" in line


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCli:
    def test_log_subcommand_exits_0(self, tmp_path, monkeypatch):
        mod = _load(tmp_path)
        monkeypatch.setattr(mod, "INVOCATION_LOG", tmp_path / "invocations.jsonl")
        rc = mod.main(["log", "--command", "/go", "--outcome", "ok"])
        assert rc == 0

    def test_tail_subcommand_exits_0(self, tmp_path, monkeypatch, capsys):
        mod = _load(tmp_path)
        monkeypatch.setattr(mod, "INVOCATION_LOG", tmp_path / "invocations.jsonl")
        mod.log_invocation("/audit", "ok", log_path=mod.INVOCATION_LOG)
        rc = mod.main(["tail", "--n", "5"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)

    def test_summarize_subcommand_exits_0(self, tmp_path, monkeypatch, capsys):
        mod = _load(tmp_path)
        monkeypatch.setattr(mod, "INVOCATION_LOG", tmp_path / "invocations.jsonl")
        monkeypatch.setattr(mod, "LATEST_JSON", tmp_path / "latest.json")
        mod.log_invocation("/explain", "ok", log_path=mod.INVOCATION_LOG)
        rc = mod.main(["summarize"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "total_invocations" in data

    def test_log_with_all_options(self, tmp_path, monkeypatch, capsys):
        mod = _load(tmp_path)
        monkeypatch.setattr(mod, "INVOCATION_LOG", tmp_path / "invocations.jsonl")
        rc = mod.main(
            [
                "log",
                "--command",
                "/ship",
                "--outcome",
                "ok",
                "--mode",
                "execute",
                "--duration-ms",
                "500",
                "--detail",
                "shipped cleanly",
                "--run-id",
                "tel_testrun1",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["mode"] == "execute"
        assert data["duration_ms"] == 500
        assert data["run_id"] == "tel_testrun1"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
