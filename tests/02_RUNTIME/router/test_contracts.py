"""Tests for router contracts: data classes, enums, validation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "02_RUNTIME"))

import pytest

from router.contracts import (
    TaskType,
    PrivacyClass,
    ConfidenceBand,
    OutputType,
    RouteInput,
    RouteConstraints,
    RouteConfidence,
    RouteAudit,
    RouteRequest,
    RouteUsage,
    RouteOutput,
    RouteLogs,
    RouteResponse,
    DeniedResource,
    ContextGateResult,
    RoutingContext,
    OllamaEndpoint,
)


# ── Enums ───────────────────────────────────────────────────────────────────


def test_task_type_values():
    assert TaskType.CLASSIFICATION.value == "classification"
    assert TaskType.CODING.value == "coding"
    assert TaskType.RESEARCH.value == "research"


def test_task_type_from_string():
    assert TaskType("planning") == TaskType.PLANNING
    assert TaskType("review") == TaskType.REVIEW


def test_task_type_invalid_raises():
    with pytest.raises(ValueError):
        TaskType("nonexistent")


def test_privacy_class_values():
    assert PrivacyClass.P0.value == "P0"
    assert PrivacyClass.P3.value == "P3"
    assert PrivacyClass.P4.value == "P4"


def test_privacy_class_from_string():
    assert PrivacyClass("P1") == PrivacyClass.P1
    assert PrivacyClass("P2") == PrivacyClass.P2


def test_confidence_band_values():
    assert ConfidenceBand.VERY_HIGH.value == "very_high"
    assert ConfidenceBand.BLOCKED.value == "blocked"


def test_output_type_values():
    assert OutputType.TEXT.value == "text"
    assert OutputType.ERROR.value == "error"


# ── RouteInput ───────────────────────────────────────────────────────────────


def test_route_input_defaults():
    inp = RouteInput()
    assert inp.messages == []
    assert inp.files == []
    assert inp.metadata == {}


def test_route_input_with_messages():
    msgs = [{"role": "user", "content": "hello"}]
    inp = RouteInput(messages=msgs)
    assert inp.messages == msgs


# ── RouteConstraints ─────────────────────────────────────────────────────────


def test_route_constraints_defaults():
    c = RouteConstraints()
    assert c.privacy_class == PrivacyClass.P1
    assert c.max_cost_usd == 0.25
    assert c.max_tokens == 8000
    assert c.allow_cloud is True
    assert c.allow_openhuman is False


def test_route_constraints_custom():
    c = RouteConstraints(
        privacy_class=PrivacyClass.P2,
        max_cost_usd=1.0,
        allow_cloud=False,
    )
    assert c.privacy_class == PrivacyClass.P2
    assert c.max_cost_usd == 1.0
    assert c.allow_cloud is False


# ── RouteConfidence ──────────────────────────────────────────────────────────


def test_route_confidence_defaults():
    rc = RouteConfidence()
    assert rc.score == 0.0
    assert rc.band == ConfidenceBand.BLOCKED
    assert rc.reason == ""


def test_route_confidence_custom():
    rc = RouteConfidence(score=85.0, band=ConfidenceBand.HIGH, reason="good fit")
    assert rc.score == 85.0
    assert rc.band == ConfidenceBand.HIGH


# ── RouteAudit ───────────────────────────────────────────────────────────────


def test_route_audit_defaults():
    a = RouteAudit()
    assert a.caller == "unknown"
    assert a.human_gate_required is False


def test_route_audit_custom():
    a = RouteAudit(caller="ci-bot", repo="chromatic", human_gate_required=True)
    assert a.caller == "ci-bot"
    assert a.human_gate_required is True


# ── RouteRequest ─────────────────────────────────────────────────────────────


def test_route_request_required_fields():
    req = RouteRequest(
        request_id="req-1",
        task_id="task-1",
        task_type=TaskType.CODING,
        objective="write tests",
    )
    assert req.request_id == "req-1"
    assert req.task_type == TaskType.CODING
    assert req.preferred_provider == "auto"
    assert req.fallback_chain == []


def test_route_request_with_all_fields():
    req = RouteRequest(
        request_id="req-2",
        task_id="task-2",
        task_type=TaskType.PLANNING,
        objective="plan sprint",
        input=RouteInput(messages=[{"role": "user", "content": "help"}]),
        constraints=RouteConstraints(privacy_class=PrivacyClass.P2),
        confidence=RouteConfidence(score=80.0, band=ConfidenceBand.HIGH),
        preferred_provider="mock",
        fallback_chain=["ollama"],
        audit=RouteAudit(caller="agent"),
    )
    assert req.preferred_provider == "mock"
    assert req.fallback_chain == ["ollama"]
    assert req.constraints.privacy_class == PrivacyClass.P2


# ── RouteOutput ──────────────────────────────────────────────────────────────


def test_route_output_defaults():
    out = RouteOutput()
    assert out.type == OutputType.TEXT
    assert out.content == ""


def test_route_output_error():
    out = RouteOutput(type=OutputType.ERROR, content="something failed")
    assert out.type == OutputType.ERROR
    assert "failed" in out.content


# ── RouteLogs ────────────────────────────────────────────────────────────────


def test_route_logs_defaults():
    logs = RouteLogs()
    assert logs.policy_checks == []
    assert logs.warnings == []
    assert logs.errors == []


def test_route_logs_mutability():
    logs = RouteLogs()
    logs.policy_checks.append("check A")
    logs.errors.append("err X")
    assert "check A" in logs.policy_checks
    assert "err X" in logs.errors


def test_two_logs_are_independent():
    a = RouteLogs()
    b = RouteLogs()
    a.warnings.append("w1")
    assert b.warnings == []


# ── RouteResponse ────────────────────────────────────────────────────────────


def test_route_response_required_field():
    resp = RouteResponse(request_id="r-1")
    assert resp.request_id == "r-1"
    assert resp.selected_provider == ""
    assert resp.fallback_used is False
    assert resp.privacy_class == PrivacyClass.P0


def test_route_response_optional_fields():
    resp = RouteResponse(
        request_id="r-2",
        selected_provider="mock",
        route_reason="ok",
        confidence_score=90.0,
        fallback_used=False,
    )
    assert resp.confidence_score == 90.0
    assert resp.selected_provider == "mock"


# ── DeniedResource / ContextGateResult ───────────────────────────────────────


def test_denied_resource_fields():
    dr = DeniedResource(resource_id="tool:bash", reason="budget exceeded")
    assert dr.resource_id == "tool:bash"
    assert "budget" in dr.reason


def test_context_gate_result_ok():
    cgr = ContextGateResult(ok=True, allowed_resources=["tool:read"])
    assert cgr.ok is True
    assert "tool:read" in cgr.allowed_resources


def test_context_gate_result_blocked():
    cgr = ContextGateResult(
        ok=False,
        denied_resources=[DeniedResource("tool:bash", "budget")],
        logs=["blocked"],
    )
    assert cgr.ok is False
    assert len(cgr.denied_resources) == 1


# ── OllamaEndpoint / RoutingContext ──────────────────────────────────────────


def test_ollama_endpoint_defaults():
    ep = OllamaEndpoint(host="192.168.1.10")
    assert ep.port == 11434
    assert ep.enabled is True


def test_ollama_endpoint_custom():
    ep = OllamaEndpoint(host="10.0.0.1", port=9999, enabled=False)
    assert ep.port == 9999
    assert ep.enabled is False


def test_ollama_endpoint_is_frozen():
    ep = OllamaEndpoint(host="localhost")
    with pytest.raises((AttributeError, TypeError)):
        ep.host = "other"  # type: ignore[misc]


def test_routing_context_defaults():
    ctx = RoutingContext(objective="do something")
    assert ctx.privacy_class == PrivacyClass.P1
    assert ctx.speed_mode == "balance"
    assert ctx.internet_reachable is True
    assert ctx.gpu_available is False
    assert ctx.ollama_local_reachable is False


def test_routing_context_is_frozen():
    ctx = RoutingContext(objective="test")
    with pytest.raises((AttributeError, TypeError)):
        ctx.objective = "changed"  # type: ignore[misc]


def test_routing_context_with_endpoints():
    ep = OllamaEndpoint(host="server1")
    ctx = RoutingContext(
        objective="heavy task",
        device_type="desktop",
        gpu_available=True,
        remote_ollama_endpoints=(ep,),
        privacy_class=PrivacyClass.P2,
    )
    assert ctx.device_type == "desktop"
    assert ctx.gpu_available is True
    assert len(ctx.remote_ollama_endpoints) == 1
    assert ctx.privacy_class == PrivacyClass.P2
