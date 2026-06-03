"""End-to-end integration tests for the full mission lifecycle.

Tests exercise multiple layers together:
  intake -> router -> gates -> magnets -> provider dispatch -> result recorded

Real router/magnet/gate logic is used throughout; only LLM provider calls
are mocked via fake adapters.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest

# sys.path is set by tests/conftest.py (inserts 02_RUNTIME)

from router.router import ChromaticRouter
from router.contracts import (
    ConfidenceBand,
    OutputType,
    PrivacyClass,
    RouteAudit,
    RouteConfidence,
    RouteConstraints,
    RouteInput,
    RouteOutput,
    RouteRequest,
    RouteResponse,
    TaskType,
)
from router.adapters.base import AdapterHealth, BaseAdapter
from router.confidence import ConfidenceGate
from magnets.magnet_orchestrator import MagnetOrchestrator
from magnets.base_magnet import MagnetEvent
from intake.queue import (
    append_entry,
    list_queued,
    normalize_entry,
    record_status,
    validate_entry,
)


# ---------------------------------------------------------------------------
# Shared fake adapter
# ---------------------------------------------------------------------------


class FakeAdapter(BaseAdapter):
    """Deterministic stub adapter that never calls external services."""

    def __init__(
        self,
        name: str,
        *,
        mode: str = "ok",
        enabled: bool = True,
        response_content: str = "",
    ) -> None:
        super().__init__(name, {"enabled": enabled})
        self.mode = mode
        self.calls: list[RouteRequest] = []
        self._response_content = response_content or f"ok from {name}"

    async def complete(self, req: RouteRequest) -> RouteResponse:
        self.calls.append(req)
        if self.mode == "raise":
            raise RuntimeError(f"{self.name} simulated failure")
        if self.mode == "error":
            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                output=RouteOutput(type=OutputType.ERROR, content="adapter error"),
            )
        return RouteResponse(
            request_id=req.request_id,
            selected_provider=self.name,
            output=RouteOutput(type=OutputType.TEXT, content=self._response_content),
        )

    async def health(self) -> AdapterHealth:
        return AdapterHealth(reachable=True, latency_ms=1)


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _make_request(
    *,
    privacy_class: PrivacyClass = PrivacyClass.P1,
    confidence_score: float = 80.0,
    preferred_provider: str = "mock",
    task_type: TaskType = TaskType.CLASSIFICATION,
    objective: str = "integration test objective",
    max_cost_usd: float = 1.0,
    fallback_chain: list[str] | None = None,
    human_gate_required: bool = False,
    messages: list[dict[str, Any]] | None = None,
    request_id: str | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id or str(uuid.uuid4()),
        task_id=str(uuid.uuid4()),
        task_type=task_type,
        objective=objective,
        input=RouteInput(messages=messages or []),
        constraints=RouteConstraints(
            privacy_class=privacy_class,
            max_cost_usd=max_cost_usd,
        ),
        confidence=RouteConfidence(
            score=confidence_score,
            band=ConfidenceGate.band_from_score(confidence_score),
        ),
        preferred_provider=preferred_provider,
        fallback_chain=fallback_chain or [],
        audit=RouteAudit(caller="integration_test", human_gate_required=human_gate_required),
    )


def _router_with_mock(response_content: str = "") -> ChromaticRouter:
    mock = FakeAdapter("mock", mode="ok", response_content=response_content)
    return ChromaticRouter(adapters={"mock": mock})


# ---------------------------------------------------------------------------
# 1. Intake queue integration
# ---------------------------------------------------------------------------


class TestIntakeQueueIntegration:
    """Verify tasks can be submitted, validated, and read back from the queue."""

    def test_append_and_read_back(self, tmp_path: Path) -> None:
        queue_file = tmp_path / "queue.jsonl"
        entry = append_entry(
            {
                "id": "intake-abc001",
                "source": "manual",
                "kind": "goal",
                "status": "queued",
                "title": "Build new feature",
                "goal": "Implement auth module",
            },
            path=queue_file,
        )
        assert entry.id == "intake-abc001"
        assert entry.status == "queued"

        queued = list_queued(path=queue_file)
        assert len(queued) == 1
        assert queued[0].id == "intake-abc001"
        assert queued[0].goal == "Implement auth module"

    def test_status_transition_recorded(self, tmp_path: Path) -> None:
        queue_file = tmp_path / "queue.jsonl"
        entry = append_entry(
            {
                "id": "intake-abc002",
                "source": "agent_lead",
                "kind": "bead_dispatch",
                "status": "queued",
                "title": "Fix login bug",
                "bead_id": "bead-001",
            },
            path=queue_file,
        )
        updated = record_status(entry, "processing", path=queue_file)
        assert updated.status == "processing"

        # After processing transition the entry is no longer in queued list
        queued = list_queued(path=queue_file)
        assert all(e.id != "intake-abc002" or e.status != "queued" for e in queued)

    def test_invalid_entry_raises(self) -> None:
        errors = validate_entry(
            {
                "id": "x",
                "source": "invalid_source",
                "kind": "goal",
                "status": "queued",
                "title": "t",
                "queued_at": "2025-01-01T00:00:00Z",
                "goal": "g",
            }
        )
        assert any("invalid source" in e for e in errors)

    def test_normalize_fills_defaults(self) -> None:
        data = normalize_entry({"source": "manual", "kind": "goal", "title": "t", "goal": "g"})
        assert data["status"] == "queued"
        assert data["priority"] == "P2"
        assert data["tier"] == 3
        assert data["id"].startswith("intake-")

    def test_bead_dispatch_auto_sets_bead_id(self) -> None:
        data = normalize_entry(
            {
                "id": "bd-001",
                "source": "bead_hook",
                "kind": "bead_dispatch",
                "title": "t",
            }
        )
        assert data["bead_id"] == "bd-001"


# ---------------------------------------------------------------------------
# 2. Full happy path: intake -> router -> mock provider -> result
# ---------------------------------------------------------------------------


class TestFullMissionHappyPath:
    """Task submitted to intake then routed through mock provider successfully."""

    @pytest.mark.asyncio
    async def test_task_dispatched_successfully(self, tmp_path: Path) -> None:
        queue_file = tmp_path / "queue.jsonl"
        # Step 1: submit to intake
        entry = append_entry(
            {
                "id": "intake-happy001",
                "source": "manual",
                "kind": "goal",
                "status": "queued",
                "title": "Classify user intent",
                "goal": "Classify intent for the new user message",
            },
            path=queue_file,
        )
        assert entry.status == "queued"

        # Step 2: router dispatches via mock adapter
        router = _router_with_mock(response_content="intent=greeting")
        req = _make_request(
            objective=entry.goal,
            task_type=TaskType.CLASSIFICATION,
            confidence_score=85.0,
            preferred_provider="mock",
        )
        resp = await router.route(req)

        assert resp.output.type == OutputType.TEXT
        assert "intent=greeting" in resp.output.content
        assert resp.selected_provider == "mock"
        assert resp.confidence_score == 85.0

        # Step 3: record processed status
        updated = record_status(entry, "processed", path=queue_file)
        assert updated.status == "processed"
        assert updated.processed_at != ""

    @pytest.mark.asyncio
    async def test_response_carries_privacy_class(self) -> None:
        router = _router_with_mock()
        req = _make_request(privacy_class=PrivacyClass.P2)
        resp = await router.route(req)
        assert resp.privacy_class == PrivacyClass.P2

    @pytest.mark.asyncio
    async def test_response_has_latency_set(self) -> None:
        router = _router_with_mock()
        req = _make_request()
        resp = await router.route(req)
        assert resp.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_all_magnets_pass_produces_proceed_recommendation(self) -> None:
        """All-positive magnet events produce a high-score proceed recommendation."""
        orchestrator = MagnetOrchestrator()
        events: list[MagnetEvent] = [
            MagnetEvent(
                mission_id="m-happy",
                magnet_name="confidence_magnet",
                inflection_point="plan_complete",
                observed_signal={"confidence_delta": 5.0},
                confidence_delta=5.0,
                risk_delta=0.0,
                recommended_action="none",
            ),
            MagnetEvent(
                mission_id="m-happy",
                magnet_name="validation_magnet",
                inflection_point="tests_complete",
                observed_signal={"tests_passed": True},
                confidence_delta=3.0,
                risk_delta=0.0,
                recommended_action="none",
            ),
        ]
        report = orchestrator.process("m-happy", events)

        assert report.score > 75
        assert report.recommendation in ("proceed", "proceed_reversible_only")

    @pytest.mark.asyncio
    async def test_router_logs_policy_checks(self) -> None:
        router = _router_with_mock()
        req = _make_request(confidence_score=90.0)
        resp = await router.route(req)
        assert len(resp.logs.policy_checks) > 0


# ---------------------------------------------------------------------------
# 3. Budget exceeded -> router blocks -> task rejected
# ---------------------------------------------------------------------------


class TestBudgetGateBlocking:
    """Budget exceeded causes task rejection with clear error."""

    @pytest.mark.asyncio
    async def test_budget_exceeded_blocks_route(self, monkeypatch: pytest.MonkeyPatch) -> None:
        router = _router_with_mock()
        req = _make_request(max_cost_usd=0.0, confidence_score=80.0)
        monkeypatch.setenv("CHROMATIC_ROUTER_DAILY_SPEND", "999.0")
        resp = await router.route(req)
        assert resp.route_reason == "budget_gate_blocked"
        assert resp.output.type == OutputType.ERROR

    @pytest.mark.asyncio
    async def test_budget_blocked_error_in_logs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        router = _router_with_mock()
        req = _make_request(max_cost_usd=0.0, confidence_score=80.0)
        monkeypatch.setenv("CHROMATIC_ROUTER_DAILY_SPEND", "999.0")
        resp = await router.route(req)
        assert any("cap" in e.lower() or "budget" in e.lower() or "exceed" in e.lower() for e in resp.logs.errors)

    @pytest.mark.asyncio
    async def test_budget_block_response_has_provider_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Budget gate fires after provider selection; selected_provider should be set."""
        router = _router_with_mock()
        req = _make_request(max_cost_usd=0.0, confidence_score=80.0, preferred_provider="mock")
        monkeypatch.setenv("CHROMATIC_ROUTER_DAILY_SPEND", "999.0")
        resp = await router.route(req)
        assert resp.route_reason == "budget_gate_blocked"
        assert resp.selected_provider != ""

    @pytest.mark.asyncio
    async def test_budget_within_limits_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CHROMATIC_ROUTER_DAILY_SPEND", "0.0")
        router = _router_with_mock()
        req = _make_request(max_cost_usd=5.0, confidence_score=80.0)
        resp = await router.route(req)
        assert resp.route_reason != "budget_gate_blocked"
        assert resp.output.type == OutputType.TEXT


# ---------------------------------------------------------------------------
# 4. Privacy gate: P3/P4 routes blocked
# ---------------------------------------------------------------------------


class TestPrivacyGateBlocking:
    """P3 and unguarded P4 tasks must be blocked by the privacy gate."""

    @pytest.mark.asyncio
    async def test_p3_task_blocked(self) -> None:
        router = _router_with_mock()
        req = _make_request(privacy_class=PrivacyClass.P3, confidence_score=95.0)
        resp = await router.route(req)
        assert resp.route_reason == "privacy_gate_blocked"
        assert resp.output.type == OutputType.ERROR

    @pytest.mark.asyncio
    async def test_p3_error_mentions_p3(self) -> None:
        router = _router_with_mock()
        req = _make_request(privacy_class=PrivacyClass.P3, confidence_score=95.0)
        resp = await router.route(req)
        assert any("P3" in e for e in resp.logs.errors)

    @pytest.mark.asyncio
    async def test_p4_blocked_without_human_gate(self) -> None:
        router = _router_with_mock()
        req = _make_request(
            privacy_class=PrivacyClass.P4,
            confidence_score=95.0,
            human_gate_required=False,
        )
        resp = await router.route(req)
        assert resp.route_reason == "privacy_gate_blocked"

    @pytest.mark.asyncio
    async def test_p4_passes_with_human_gate(self) -> None:
        router = _router_with_mock()
        req = _make_request(
            privacy_class=PrivacyClass.P4,
            confidence_score=95.0,
            human_gate_required=True,
        )
        resp = await router.route(req)
        assert resp.route_reason != "privacy_gate_blocked"

    @pytest.mark.asyncio
    async def test_p1_passes_privacy_gate(self) -> None:
        router = _router_with_mock()
        req = _make_request(privacy_class=PrivacyClass.P1, confidence_score=80.0)
        resp = await router.route(req)
        assert resp.route_reason != "privacy_gate_blocked"
        assert resp.output.type == OutputType.TEXT

    @pytest.mark.asyncio
    async def test_p2_passes_privacy_gate(self) -> None:
        router = _router_with_mock()
        req = _make_request(privacy_class=PrivacyClass.P2, confidence_score=80.0)
        resp = await router.route(req)
        assert resp.route_reason != "privacy_gate_blocked"


# ---------------------------------------------------------------------------
# 5. Confidence too low -> route blocked
# ---------------------------------------------------------------------------


class TestConfidenceGateBlocking:
    """Confidence below 60 must be rejected before provider selection."""

    @pytest.mark.asyncio
    async def test_score_below_60_blocked(self) -> None:
        router = _router_with_mock()
        req = _make_request(confidence_score=45.0)
        resp = await router.route(req)
        assert resp.route_reason == "confidence_gate_blocked"
        assert resp.output.type == OutputType.ERROR

    @pytest.mark.asyncio
    async def test_score_at_60_allowed(self) -> None:
        router = _router_with_mock()
        req = _make_request(confidence_score=60.0)
        resp = await router.route(req)
        assert resp.route_reason != "confidence_gate_blocked"

    @pytest.mark.asyncio
    async def test_score_0_blocked(self) -> None:
        router = _router_with_mock()
        req = _make_request(confidence_score=0.0)
        resp = await router.route(req)
        assert resp.route_reason == "confidence_gate_blocked"

    @pytest.mark.asyncio
    async def test_low_confidence_magnet_reflects_risk(self) -> None:
        """Magnet with negative confidence delta should not get a 'proceed' recommendation."""
        orchestrator = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="m-lowconf",
                magnet_name="confidence_magnet",
                inflection_point="plan_complete",
                observed_signal={"confidence_delta": -10.0},
                confidence_delta=-10.0,
                risk_delta=0.2,
                recommended_action="review",
            ),
        ]
        report = orchestrator.process("m-lowconf", events)
        assert report.recommendation in ("replan", "review", "halt", "proceed_reversible_only")
        assert report.score < 80

    @pytest.mark.asyncio
    async def test_fallback_chain_tried_before_error(self) -> None:
        """Primary returns an error response; mock fallback should succeed."""
        primary = FakeAdapter("primary", mode="error")
        mock_fb = FakeAdapter("mock", mode="ok", response_content="fallback succeeded")
        router = ChromaticRouter(adapters={"primary": primary, "mock": mock_fb})
        req = _make_request(
            preferred_provider="primary",
            fallback_chain=["mock"],
            confidence_score=75.0,
        )
        resp = await router.route(req)
        assert resp.output.type == OutputType.TEXT
        assert resp.selected_provider == "mock"


# ---------------------------------------------------------------------------
# 6. All magnets pass -> task dispatched successfully
# ---------------------------------------------------------------------------


class TestAllMagnetsPassDispatch:
    """All-positive magnet signals -> orchestrator says proceed -> router dispatches."""

    @pytest.mark.asyncio
    async def test_all_positive_magnets_then_route(self, tmp_path: Path) -> None:
        orchestrator = MagnetOrchestrator()
        mission_id = "m-full-e2e"
        events: list[MagnetEvent] = [
            MagnetEvent(
                mission_id=mission_id,
                magnet_name="intake_magnet",
                inflection_point="task_received",
                observed_signal={"task_valid": True},
                confidence_delta=2.0,
                risk_delta=0.0,
                recommended_action="none",
            ),
            MagnetEvent(
                mission_id=mission_id,
                magnet_name="confidence_magnet",
                inflection_point="plan_complete",
                observed_signal={"confidence_delta": 5.0},
                confidence_delta=5.0,
                risk_delta=0.0,
                recommended_action="none",
            ),
            MagnetEvent(
                mission_id=mission_id,
                magnet_name="validation_magnet",
                inflection_point="tests_complete",
                observed_signal={"tests_passed": True},
                confidence_delta=3.0,
                risk_delta=0.0,
                recommended_action="none",
            ),
            MagnetEvent(
                mission_id=mission_id,
                magnet_name="execution_magnet",
                inflection_point="execution_complete",
                observed_signal={"exit_code": 0},
                confidence_delta=1.0,
                risk_delta=0.0,
                recommended_action="none",
            ),
        ]
        report = orchestrator.process(mission_id, events)
        assert report.score > 75
        assert report.recommendation in ("proceed", "proceed_reversible_only")

        # Router dispatch should also succeed
        router = _router_with_mock(response_content="task complete")
        req = _make_request(
            objective="Complete the feature implementation",
            task_type=TaskType.CODING,
            confidence_score=85.0,
        )
        resp = await router.route(req)
        assert resp.output.type == OutputType.TEXT
        assert "task complete" in resp.output.content
        assert resp.route_reason not in (
            "privacy_gate_blocked",
            "confidence_gate_blocked",
            "budget_gate_blocked",
        )

    @pytest.mark.asyncio
    async def test_multi_task_type_dispatch(self) -> None:
        """Router handles all task types without crashing."""
        router = _router_with_mock()
        for task_type in TaskType:
            req = _make_request(task_type=task_type, confidence_score=80.0)
            resp = await router.route(req)
            assert isinstance(resp, RouteResponse), f"Failed for task_type={task_type}"

    @pytest.mark.asyncio
    async def test_result_request_id_preserved(self) -> None:
        router = _router_with_mock()
        req_id = "stable-id-9999"
        req = _make_request(request_id=req_id, confidence_score=80.0)
        resp = await router.route(req)
        assert resp.request_id == req_id


# ---------------------------------------------------------------------------
# 7. Magnet halt signal -> orchestrator recommendation = halt
# ---------------------------------------------------------------------------


class TestMagnetHaltSignal:
    def test_halt_action_triggers_halt_recommendation(self) -> None:
        orchestrator = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="m-halt",
                magnet_name="security_magnet",
                inflection_point="post_execution",
                observed_signal={"violation": "secret_exposed"},
                risk_delta=0.8,
                confidence_delta=-5.0,
                recommended_action="halt",
            ),
        ]
        report = orchestrator.process("m-halt", events)
        assert report.recommendation == "halt"
        assert report.risk_score >= 0.5

    def test_multiple_halt_events_accumulate_risk(self) -> None:
        orchestrator = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="m-multi-halt",
                magnet_name="security_magnet",
                inflection_point="post_execution",
                observed_signal={},
                risk_delta=0.3,
                recommended_action="halt",
            ),
            MagnetEvent(
                mission_id="m-multi-halt",
                magnet_name="scope_magnet",
                inflection_point="post_execution",
                observed_signal={},
                risk_delta=0.4,
                recommended_action="halt",
            ),
        ]
        report = orchestrator.process("m-multi-halt", events)
        assert report.recommendation == "halt"
        assert report.correlated["halt_actions"] == 2
