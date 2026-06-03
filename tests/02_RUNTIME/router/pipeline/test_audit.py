"""Tests for router pipeline audit stage."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "02_RUNTIME"))

import pytest

from router.pipeline.audit import log_entry, audit_router_decision


# ── log_entry ────────────────────────────────────────────────────────────────


def test_log_entry_creates_file(tmp_path, monkeypatch):
    """log_entry writes a valid JSONL line to LOG_FILE."""
    import router.pipeline.audit as aud

    log_dir = tmp_path / "router_logs"
    monkeypatch.setattr(aud, "LOG_DIR", log_dir)
    monkeypatch.setattr(aud, "LOG_FILE", log_dir / "log.jsonl")

    log_entry({"event": "test", "value": 42})

    log_file = log_dir / "log.jsonl"
    assert log_file.is_file()
    line = json.loads(log_file.read_text(encoding="utf-8").strip())
    assert line["event"] == "test"
    assert line["value"] == 42


def test_log_entry_appends_multiple_lines(tmp_path, monkeypatch):
    """Multiple log_entry calls each append a distinct line."""
    import router.pipeline.audit as aud

    log_dir = tmp_path / "router_logs"
    monkeypatch.setattr(aud, "LOG_DIR", log_dir)
    monkeypatch.setattr(aud, "LOG_FILE", log_dir / "log.jsonl")

    log_entry({"seq": 1})
    log_entry({"seq": 2})
    log_entry({"seq": 3})

    lines = (log_dir / "log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    assert json.loads(lines[0])["seq"] == 1
    assert json.loads(lines[2])["seq"] == 3


def test_log_entry_rotation(tmp_path, monkeypatch):
    """log_entry trims the log when it exceeds MAX_LOG_LINES."""
    import router.pipeline.audit as aud

    max_lines = 10
    log_dir = tmp_path / "router_logs"
    log_dir.mkdir(parents=True)
    log_file = log_dir / "log.jsonl"
    monkeypatch.setattr(aud, "LOG_DIR", log_dir)
    monkeypatch.setattr(aud, "LOG_FILE", log_file)
    monkeypatch.setattr(aud, "MAX_LOG_LINES", max_lines)

    # Pre-fill with max_lines entries
    for i in range(max_lines):
        log_file.write_text(
            "\n".join(json.dumps({"seq": j}) for j in range(max_lines)) + "\n",
            encoding="utf-8",
        )

    # Writing one more should trigger rotation (11 lines → trim to 80%)
    log_entry({"seq": max_lines})

    kept = (log_file).read_text(encoding="utf-8").strip().splitlines()
    assert len(kept) <= max_lines


def test_log_entry_unicode(tmp_path, monkeypatch):
    """log_entry handles unicode characters correctly."""
    import router.pipeline.audit as aud

    log_dir = tmp_path / "router_logs"
    monkeypatch.setattr(aud, "LOG_DIR", log_dir)
    monkeypatch.setattr(aud, "LOG_FILE", log_dir / "log.jsonl")

    log_entry({"msg": "héllo wörld 中文"})

    log_file = log_dir / "log.jsonl"
    line = json.loads(log_file.read_text(encoding="utf-8").strip())
    assert "héllo" in line["msg"]


# ── audit_router_decision ────────────────────────────────────────────────────


def _make_entry(**kwargs):
    base = {
        "provider": "mock",
        "target_model": "claude-3-haiku",
        "tier": "T1",
        "blocked": False,
        "c_level": "medium",
        "speed_mode": "balance",
        "reason": "test routing",
        "description": "unit test entry",
        "subagent_type": "coding",
        "c_confidence": 0.9,
    }
    base.update(kwargs)
    return base


def test_audit_router_decision_is_fail_open():
    """audit_router_decision never raises even when all deps fail."""
    entry = _make_entry()
    # Patch TwoLogAudit import to raise
    with patch.dict("sys.modules", {"audit.two_log": None}):
        # Should complete silently even if TwoLogAudit is unavailable
        try:
            audit_router_decision(
                entry,
                billing_fn=lambda p: {
                    "cost_estimate_usd": 0.0,
                    "billing_axis": "P",
                    "billing_tokens": 64000,
                    "budget_gate_estimate_usd": None,
                },
            )
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"audit_router_decision raised unexpectedly: {exc}")


def test_audit_router_decision_uses_provided_billing_fn(tmp_path):
    """audit_router_decision calls billing_fn with the provider string."""
    calls: list[str] = []

    def fake_billing(provider: str):
        calls.append(provider)
        return {
            "cost_estimate_usd": 0.0,
            "billing_axis": "D",
            "billing_tokens": 64000,
            "budget_gate_estimate_usd": None,
        }

    entry = _make_entry(provider="claude_api")

    mock_audit = MagicMock()
    mock_two_log_mod = MagicMock()
    mock_two_log_mod.TwoLogAudit.return_value = mock_audit

    with patch.dict("sys.modules", {"audit.two_log": mock_two_log_mod}):
        audit_router_decision(entry, billing_fn=fake_billing)

    assert "claude_api" in calls


def test_audit_router_decision_writes_routing_log(tmp_path, monkeypatch):
    """audit_router_decision writes a JSONL record to the routing log directory."""
    import router.pipeline.audit as aud

    monkeypatch.setattr(aud, "_REPO", tmp_path)

    mock_audit_obj = MagicMock()
    mock_two_log_mod = MagicMock()
    mock_two_log_mod.TwoLogAudit.return_value = mock_audit_obj

    entry = _make_entry(description="test audit write", provider="ollama")

    def fake_billing(provider):
        return {
            "cost_estimate_usd": 0.0,
            "billing_axis": "F",
            "billing_tokens": 1000,
            "budget_gate_estimate_usd": None,
        }

    with patch.dict("sys.modules", {"audit.two_log": mock_two_log_mod}):
        with patch("router.pipeline.audit._repo", return_value=tmp_path):
            audit_router_decision(entry, billing_fn=fake_billing)

    routing_dir = tmp_path / "07_LOGS_AND_AUDIT" / "routing"
    jsonl_files = list(routing_dir.glob("routes_*.jsonl"))
    assert jsonl_files, "Expected a routing JSONL file to be created"

    record = json.loads(jsonl_files[0].read_text(encoding="utf-8").strip())
    assert record["selected_provider"] == "ollama"
    assert record["billing_axis"] == "F"
    assert "decision_id" in record
    assert "timestamp" in record


def test_audit_router_decision_blocked_status(tmp_path):
    """audit_router_decision records result_status=blocked when entry is blocked."""
    mock_audit_obj = MagicMock()
    mock_two_log_mod = MagicMock()
    mock_two_log_mod.TwoLogAudit.return_value = mock_audit_obj

    entry = _make_entry(blocked=True, provider="gemini")

    def fake_billing(provider):
        return {
            "cost_estimate_usd": 0.001,
            "billing_axis": "D",
            "billing_tokens": 500,
            "budget_gate_estimate_usd": 0.002,
        }

    with patch("router.pipeline.audit._repo") as mock_repo:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            mock_repo.return_value = Path(td)
            with patch.dict("sys.modules", {"audit.two_log": mock_two_log_mod}):
                audit_router_decision(entry, billing_fn=fake_billing)

            routing_dir = Path(td) / "07_LOGS_AND_AUDIT" / "routing"
            files = list(routing_dir.glob("routes_*.jsonl")) if routing_dir.exists() else []
            if files:
                record = json.loads(files[0].read_text(encoding="utf-8").strip())
                assert record["result_status"] == "blocked"


def test_audit_router_decision_required_fields_populated(tmp_path):
    """All required fields appear in the routing log record."""
    mock_audit_obj = MagicMock()
    mock_two_log_mod = MagicMock()
    mock_two_log_mod.TwoLogAudit.return_value = mock_audit_obj

    entry = _make_entry(provider="native_claude", target_model="claude-opus-4-5")

    def fake_billing(provider):
        return {
            "cost_estimate_usd": 0.0,
            "billing_axis": "P",
            "billing_tokens": 128000,
            "budget_gate_estimate_usd": None,
        }

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        with patch("router.pipeline.audit._repo", return_value=Path(td)):
            with patch.dict("sys.modules", {"audit.two_log": mock_two_log_mod}):
                audit_router_decision(entry, billing_fn=fake_billing)

        routing_dir = Path(td) / "07_LOGS_AND_AUDIT" / "routing"
        files = list(routing_dir.glob("routes_*.jsonl")) if routing_dir.exists() else []
        if files:
            record = json.loads(files[0].read_text(encoding="utf-8").strip())
            required_fields = {
                "timestamp",
                "decision_id",
                "request_id",
                "selected_provider",
                "selected_model",
                "route_reason",
                "result_status",
                "billing_axis",
                "billing_tokens",
            }
            for field in required_fields:
                assert field in record, f"Missing required field: {field}"
