"""Tests for router/observability.py — JSONL route logging with redaction."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from router.contracts import (
    ConfidenceBand,
    OutputType,
    PrivacyClass,
    RouteAudit,
    RouteConfidence,
    RouteInput,
    RouteLogs,
    RouteOutput,
    RouteRequest,
    RouteResponse,
    TaskType,
)
from router.observability import ObservabilityLogger, _BAND_TO_RISK, _GOVERNED_MODELS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_req(
    *,
    request_id: str = "req-001",
    task_id: str = "task-001",
    task_type: TaskType = TaskType.CODING,
    caller: str = "test-caller",
    repo: str = "chromatic/test",
    band: ConfidenceBand = ConfidenceBand.HIGH,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        task_id=task_id,
        task_type=task_type,
        objective="do something",
        input=RouteInput(),
        confidence=RouteConfidence(score=0.85, band=band),
        audit=RouteAudit(caller=caller, repo=repo),
    )


def _make_resp(
    *,
    request_id: str = "req-001",
    provider: str = "anthropic",
    model: str = "claude-3-opus",
    fallback: bool = False,
    confidence: float = 0.85,
    privacy: PrivacyClass = PrivacyClass.P1,
    output_type: OutputType = OutputType.TEXT,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> RouteResponse:
    return RouteResponse(
        request_id=request_id,
        selected_provider=provider,
        selected_model=model,
        route_reason="unit test",
        fallback_used=fallback,
        confidence_score=confidence,
        privacy_class=privacy,
        cost_estimate_usd=0.001,
        latency_ms=42,
        output=RouteOutput(type=output_type, content="result"),
        logs=RouteLogs(
            warnings=warnings or [],
            errors=errors or [],
        ),
    )


# ---------------------------------------------------------------------------
# Tests: log() writes JSONL with correct fields
# ---------------------------------------------------------------------------

class TestObservabilityLoggerLog:
    def test_creates_log_file_in_configured_dir(self, tmp_path: Path) -> None:
        logger = ObservabilityLogger(log_dir=tmp_path / "routes")
        req = _make_req()
        resp = _make_resp()
        logger.log(req, resp)
        files = list((tmp_path / "routes").glob("*.jsonl"))
        assert len(files) == 1

    def test_log_entry_has_required_fields(self, tmp_path: Path) -> None:
        logger = ObservabilityLogger(log_dir=tmp_path / "routes")
        req = _make_req(request_id="r1", task_id="t1", caller="agent-x", repo="org/repo")
        resp = _make_resp(
            request_id="r1",
            provider="anthropic",
            model="claude-3-haiku",
            confidence=0.9,
        )
        logger.log(req, resp)

        (log_file,) = (tmp_path / "routes").glob("*.jsonl")
        entry = json.loads(log_file.read_text(encoding="utf-8").strip())

        assert entry["request_id"] == "r1"
        assert entry["task_id"] == "t1"
        assert entry["task_type"] == TaskType.CODING.value
        assert entry["caller"] == "agent-x"
        assert entry["repo"] == "org/repo"
        assert entry["selected_provider"] == "anthropic"
        assert entry["selected_model"] == "claude-3-haiku"
        assert entry["confidence_score"] == pytest.approx(0.9)
        assert entry["fallback_used"] is False
        assert "timestamp" in entry
        assert "privacy_class" in entry
        assert "result_status" in entry

    def test_multiple_log_calls_append_lines(self, tmp_path: Path) -> None:
        logger = ObservabilityLogger(log_dir=tmp_path / "routes")
        for i in range(3):
            logger.log(_make_req(request_id=f"r{i}"), _make_resp(request_id=f"r{i}"))

        (log_file,) = (tmp_path / "routes").glob("*.jsonl")
        lines = [l for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 3

    def test_extra_fields_are_merged_into_entry(self, tmp_path: Path) -> None:
        logger = ObservabilityLogger(log_dir=tmp_path / "routes")
        logger.log(_make_req(), _make_resp(), extra={"role": "orchestrator", "tools_used": 3})

        (log_file,) = (tmp_path / "routes").glob("*.jsonl")
        entry = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert entry["role"] == "orchestrator"
        assert entry["tools_used"] == 3

    def test_warnings_and_errors_are_logged(self, tmp_path: Path) -> None:
        logger = ObservabilityLogger(log_dir=tmp_path / "routes")
        logger.log(
            _make_req(),
            _make_resp(warnings=["low conf"], errors=["timeout"]),
        )
        (log_file,) = (tmp_path / "routes").glob("*.jsonl")
        entry = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert entry["warnings"] == ["low conf"]
        assert entry["errors"] == ["timeout"]

    def test_log_creates_parent_directory_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested" / "routes"
        logger = ObservabilityLogger(log_dir=nested)
        logger.log(_make_req(), _make_resp())
        assert nested.is_dir()
        files = list(nested.glob("*.jsonl"))
        assert len(files) == 1


# ---------------------------------------------------------------------------
# Tests: redaction
# ---------------------------------------------------------------------------

class TestObservabilityLoggerRedaction:
    def test_sk_token_in_extra_is_redacted(self, tmp_path: Path) -> None:
        logger = ObservabilityLogger(log_dir=tmp_path / "routes")
        secret = "sk-" + "a" * 25
        logger.log(_make_req(), _make_resp(), extra={"api_key": secret})

        (log_file,) = (tmp_path / "routes").glob("*.jsonl")
        raw = log_file.read_text(encoding="utf-8")
        assert secret not in raw
        assert "sk-***" in raw

    def test_bearer_token_in_extra_is_redacted(self, tmp_path: Path) -> None:
        logger = ObservabilityLogger(log_dir=tmp_path / "routes")
        secret = "Bearer " + "x" * 25
        logger.log(_make_req(), _make_resp(), extra={"auth": secret})

        (log_file,) = (tmp_path / "routes").glob("*.jsonl")
        raw = log_file.read_text(encoding="utf-8")
        assert "x" * 25 not in raw
        assert "Bearer ***" in raw

    def test_ghp_token_in_extra_is_redacted(self, tmp_path: Path) -> None:
        logger = ObservabilityLogger(log_dir=tmp_path / "routes")
        secret = "ghp_" + "B" * 22
        logger.log(_make_req(), _make_resp(), extra={"token": secret})

        (log_file,) = (tmp_path / "routes").glob("*.jsonl")
        raw = log_file.read_text(encoding="utf-8")
        assert secret not in raw
        assert "ghp_***" in raw

    def test_nested_dict_in_extra_is_redacted(self, tmp_path: Path) -> None:
        logger = ObservabilityLogger(log_dir=tmp_path / "routes")
        secret = "sk-" + "z" * 30
        logger.log(_make_req(), _make_resp(), extra={"meta": {"key": secret}})

        (log_file,) = (tmp_path / "routes").glob("*.jsonl")
        raw = log_file.read_text(encoding="utf-8")
        assert secret not in raw


# ---------------------------------------------------------------------------
# Tests: governed model → AGENT_RUN_LOG
# ---------------------------------------------------------------------------

class TestAgentRunLog:
    def test_sonnet_model_triggers_agent_run_log(self, tmp_path: Path) -> None:
        agent_log = tmp_path / "agent_run.jsonl"
        logger = ObservabilityLogger(
            log_dir=tmp_path / "routes",
            agent_run_log=agent_log,
        )
        logger.log(
            _make_req(task_id="governed-task"),
            _make_resp(model="claude-sonnet-4"),
        )
        assert agent_log.is_file()
        record = json.loads(agent_log.read_text(encoding="utf-8").strip())
        assert record["task_id"] == "governed-task"
        assert "model" in record
        assert "risk_level" in record

    def test_kimi_model_triggers_agent_run_log(self, tmp_path: Path) -> None:
        agent_log = tmp_path / "agent_run.jsonl"
        logger = ObservabilityLogger(
            log_dir=tmp_path / "routes",
            agent_run_log=agent_log,
        )
        logger.log(
            _make_req(task_id="kimi-task"),
            _make_resp(model="kimi-k1-5"),
        )
        assert agent_log.is_file()

    def test_non_governed_model_does_not_write_agent_run_log(self, tmp_path: Path) -> None:
        agent_log = tmp_path / "agent_run.jsonl"
        logger = ObservabilityLogger(
            log_dir=tmp_path / "routes",
            agent_run_log=agent_log,
        )
        logger.log(_make_req(), _make_resp(model="gpt-4o"))
        assert not agent_log.exists()

    def test_agent_run_log_band_to_risk_mapping(self, tmp_path: Path) -> None:
        agent_log = tmp_path / "agent_run.jsonl"
        logger = ObservabilityLogger(
            log_dir=tmp_path / "routes",
            agent_run_log=agent_log,
        )
        logger.log(
            _make_req(band=ConfidenceBand.BLOCKED),
            _make_resp(model="claude-sonnet-4"),
            extra={"role": "coder"},
        )
        record = json.loads(agent_log.read_text(encoding="utf-8").strip())
        assert record["risk_level"] == "critical"
        assert record["role"] == "coder"

    def test_agent_run_log_very_high_band_maps_to_low_risk(self, tmp_path: Path) -> None:
        agent_log = tmp_path / "agent_run.jsonl"
        logger = ObservabilityLogger(
            log_dir=tmp_path / "routes",
            agent_run_log=agent_log,
        )
        logger.log(
            _make_req(band=ConfidenceBand.VERY_HIGH),
            _make_resp(model="claude-sonnet-4"),
        )
        record = json.loads(agent_log.read_text(encoding="utf-8").strip())
        assert record["risk_level"] == "low"

    def test_agent_run_log_extra_fields(self, tmp_path: Path) -> None:
        agent_log = tmp_path / "agent_run.jsonl"
        logger = ObservabilityLogger(
            log_dir=tmp_path / "routes",
            agent_run_log=agent_log,
        )
        extra = {
            "role": "reviewer",
            "tools_used": 5,
            "files_touched": ["foo.py", "bar.py"],
            "validation": "passed",
            "next_task": "chromatic-harness-v2-next",
        }
        logger.log(_make_req(), _make_resp(model="claude-sonnet-3"), extra=extra)
        record = json.loads(agent_log.read_text(encoding="utf-8").strip())
        assert record["tools_used"] == 5
        assert record["files_touched"] == ["foo.py", "bar.py"]
        assert record["validation"] == "passed"
        assert record["next_task"] == "chromatic-harness-v2-next"


# ---------------------------------------------------------------------------
# Tests: _BAND_TO_RISK and _GOVERNED_MODELS constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_band_to_risk_covers_all_confidence_bands(self) -> None:
        for band in ConfidenceBand:
            assert band.value in _BAND_TO_RISK, f"missing mapping for {band.value}"

    def test_governed_models_contains_expected_entries(self) -> None:
        assert "sonnet" in _GOVERNED_MODELS
        assert "kimi" in _GOVERNED_MODELS
