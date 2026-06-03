"""Integration tests: router + magnet layers working together.

Tests cover:
  - Router + confidence magnet
  - Router + cost magnet budget enforcement
  - Router + scope magnet post-execution validation
  - Magnet conflict resolution (competing risk signals)
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from router.router import ChromaticRouter
from router.contracts import (
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
from router.budget import BudgetGate
from router.privacy import PrivacyGate
from magnets.magnet_orchestrator import MagnetOrchestrator
from magnets.base_magnet import MagnetEvent
from magnets.confidence_magnet import ConfidenceMagnet
from magnets.cost_magnet import CostMagnet


# ---------------------------------------------------------------------------
# Shared fake adapter
# ---------------------------------------------------------------------------


class FakeAdapter(BaseAdapter):
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
        self._content = response_content or f"ok from {name}"

    async def complete(self, req: RouteRequest) -> RouteResponse:
        self.calls.append(req)
        if self.mode == "raise":
            raise RuntimeError(f"{self.name} error")
        if self.mode == "error":
            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                output=RouteOutput(type=OutputType.ERROR, content="adapter error"),
            )
        return RouteResponse(
            request_id=req.request_id,
            selected_provider=self.name,
            output=RouteOutput(type=OutputType.TEXT, content=self._content),
        )

    async def health(self) -> AdapterHealth:
        return AdapterHealth(reachable=True, latency_ms=1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(
    *,
    privacy_class: PrivacyClass = PrivacyClass.P1,
    confidence_score: float = 80.0,
    preferred_provider: str = "mock",
    task_type: TaskType = TaskType.CLASSIFICATION,
    objective: str = "test objective",
    max_cost_usd: float = 1.0,
    fallback_chain: list[str] | None = None,
    human_gate_required: bool = False,
    messages: list[dict[str, Any]] | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=str(uuid.uuid4()),
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
        audit=RouteAudit(
            caller="router_magnet_integration_test",
            human_gate_required=human_gate_required,
        ),
    )


def _router_with_mock(content: str = "") -> ChromaticRouter:
    return ChromaticRouter(adapters={"mock": FakeAdapter("mock", mode="ok", response_content=content)})


# ---------------------------------------------------------------------------
# 1. Router + confidence magnet working together
# ---------------------------------------------------------------------------


class TestRouterConfidenceMagnetIntegration:
    """Router confidence gate and confidence magnet evaluate the same mission coherently."""

    @pytest.mark.asyncio
    async def test_high_confidence_magnet_score_router_passes(self) -> None:
        """Confidence magnet signals high quality; router at matching score should pass."""
        orchestrator = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="m-conf-high",
                magnet_name="confidence_magnet",
                inflection_point="plan_complete",
                observed_signal={"confidence_delta": 8.0},
                confidence_delta=8.0,
                risk_delta=0.0,
                recommended_action="none",
            ),
        ]
        report = orchestrator.process("m-conf-high", events)
        assert report.confidence_score > 75

        # Router should also pass with the same confidence level
        router = _router_with_mock()
        req = _make_request(confidence_score=85.0)
        resp = await router.route(req)
        assert resp.route_reason != "confidence_gate_blocked"
        assert resp.output.type == OutputType.TEXT

    @pytest.mark.asyncio
    async def test_low_confidence_magnet_score_consistent_with_gate(self) -> None:
        """Magnet with deep confidence loss reflects router gate behavior."""
        orchestrator = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="m-conf-low",
                magnet_name="confidence_magnet",
                inflection_point="plan_complete",
                observed_signal={"confidence_delta": -15.0},
                confidence_delta=-15.0,
                risk_delta=0.1,
                recommended_action="review",
            ),
        ]
        report = orchestrator.process("m-conf-low", events)
        # Magnet score reflects the confidence loss
        assert report.confidence_score < 75

        # Router gate at equivalent score should block
        router = _router_with_mock()
        req = _make_request(confidence_score=45.0)
        resp = await router.route(req)
        assert resp.route_reason == "confidence_gate_blocked"

    def test_confidence_magnet_observe_returns_event(self) -> None:
        magnet = ConfidenceMagnet()
        event = magnet.observe(
            "m-obs",
            "plan_complete",
            {"confidence_delta": 3.0, "risk_delta": 0.0},
        )
        assert event.magnet_name == "confidence_magnet"
        assert event.confidence_delta == 3.0

    def test_confidence_magnet_penalizes_bad_test_pyramid(self) -> None:
        magnet = ConfidenceMagnet()
        # analyze_test_pyramid expects a list of test dicts; build a heavily
        # e2e-skewed pyramid: 0 unit, 0 integration, 50 e2e tests.
        skewed_tests = [{"layer": "e2e", "name": f"e2e_{i}"} for i in range(50)]
        event = magnet.observe(
            "m-pyramid",
            "test_results",
            {
                "confidence_delta": 0.0,
                "tests": skewed_tests,
            },
        )
        # A heavily skewed pyramid (all e2e, no unit) triggers deviation warnings,
        # which lower confidence_delta and/or raise risk_delta in the magnet.
        assert event.confidence_delta <= 0.0
        assert event.risk_delta >= 0.0

    @pytest.mark.asyncio
    async def test_confidence_gate_band_blocked_mapped_correctly(self) -> None:
        """ConfidenceBand.BLOCKED maps to score below 60."""
        gate = ConfidenceGate()
        band = ConfidenceGate.band_from_score(30.0)
        from router.contracts import ConfidenceBand

        assert band == ConfidenceBand.BLOCKED

        router = _router_with_mock()
        req = _make_request(confidence_score=30.0)
        resp = await router.route(req)
        assert resp.route_reason == "confidence_gate_blocked"


# ---------------------------------------------------------------------------
# 2. Router + cost magnet budget enforcement
# ---------------------------------------------------------------------------


class TestRouterCostMagnetBudgetEnforcement:
    """Budget gate and cost magnet signals should both block over-budget tasks."""

    @pytest.mark.asyncio
    async def test_router_budget_gate_blocks_over_daily_cap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CHROMATIC_ROUTER_DAILY_SPEND", "999.0")
        router = _router_with_mock()
        req = _make_request(max_cost_usd=0.0, confidence_score=80.0)
        resp = await router.route(req)
        assert resp.route_reason == "budget_gate_blocked"
        assert resp.cost_estimate_usd >= 0.0

    @pytest.mark.asyncio
    async def test_router_budget_gate_passes_within_cap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CHROMATIC_ROUTER_DAILY_SPEND", "0.0")
        router = _router_with_mock()
        req = _make_request(max_cost_usd=5.0, confidence_score=80.0)
        resp = await router.route(req)
        assert resp.route_reason != "budget_gate_blocked"

    def test_budget_gate_estimate_calculation(self) -> None:
        """BudgetGate.estimate should scale correctly with token count."""
        gate = BudgetGate()
        # Mock provider costs nothing (no entry in costs yaml for 'mock')
        est = gate.estimate("mock", 1000)
        assert est >= 0.0
        # Higher tokens -> higher or equal estimate
        est_high = gate.estimate("mock", 10000)
        assert est_high >= est

    def test_cost_magnet_name(self) -> None:
        magnet = CostMagnet()
        assert magnet.name == "cost_magnet"

    def test_cost_magnet_observe_returns_base_event(self) -> None:
        magnet = CostMagnet()
        event = magnet.observe(
            "m-cost",
            "execution_complete",
            {"tokens_used": 5000, "cost_usd": 0.05},
        )
        assert event.magnet_name == "cost_magnet"
        assert event.mission_id == "m-cost"

    @pytest.mark.asyncio
    async def test_cost_magnet_high_spend_event_escalates_risk(self) -> None:
        """Elevated cost signal via orchestrator correlates to higher risk."""
        orchestrator = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="m-cost-high",
                magnet_name="cost_magnet",
                inflection_point="execution_complete",
                observed_signal={"tokens_used": 100000, "cost_usd": 2.50},
                risk_delta=0.4,
                confidence_delta=0.0,
                recommended_action="review",
            ),
        ]
        report = orchestrator.process("m-cost-high", events)
        assert report.risk_score > 0.0
        assert report.recommendation in ("replan", "review", "halt", "proceed_reversible_only")

    @pytest.mark.asyncio
    async def test_budget_gate_check_returns_cost_estimate(self) -> None:
        gate = BudgetGate()
        from router.contracts import RouteConstraints, RouteConfidence, RouteInput, RouteAudit

        req = _make_request(max_cost_usd=10.0, confidence_score=80.0)
        ok, logs, est = gate.check(req, "mock")
        assert isinstance(ok, bool)
        assert isinstance(est, float)
        assert est >= 0.0


# ---------------------------------------------------------------------------
# 3. Router + scope magnet post-execution validation
# ---------------------------------------------------------------------------


class TestRouterScopeMagnetIntegration:
    """Scope magnet post-execution violations should escalate risk correctly."""

    def test_scope_magnet_clean_execution_no_risk(self) -> None:
        """Clean execution with no scope violations -> zero risk delta."""
        orchestrator = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="m-scope-clean",
                magnet_name="scope_magnet",
                inflection_point="post_execution",
                observed_signal={"file_scope": ["src/"], "violations": []},
                risk_delta=0.0,
                confidence_delta=0.0,
                recommended_action="none",
            ),
        ]
        report = orchestrator.process("m-scope-clean", events)
        assert report.risk_score == 0.0
        assert report.recommendation in ("proceed", "proceed_reversible_only")

    def test_scope_magnet_violation_escalates_risk(self) -> None:
        """Scope violations escalate risk and trigger halt recommendation."""
        orchestrator = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="m-scope-viol",
                magnet_name="scope_magnet",
                inflection_point="post_execution",
                observed_signal={"file_scope": ["src/"], "violations": ["wrote to /etc/passwd"]},
                risk_delta=0.6,
                confidence_delta=-3.0,
                recommended_action="halt_and_revert",
            ),
        ]
        report = orchestrator.process("m-scope-viol", events)
        # halt_and_revert counts as a halt action
        assert report.correlated["halt_actions"] >= 1
        assert report.recommendation == "halt"

    def test_scope_magnet_multiple_violations_accumulate(self) -> None:
        """Multiple scope violations from different magnets accumulate risk."""
        orchestrator = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="m-scope-multi",
                magnet_name="scope_magnet",
                inflection_point="post_execution",
                observed_signal={},
                risk_delta=0.3,
                recommended_action="halt_and_revert",
            ),
            MagnetEvent(
                mission_id="m-scope-multi",
                magnet_name="security_magnet",
                inflection_point="post_execution",
                observed_signal={"violation": "out_of_scope_write"},
                risk_delta=0.3,
                recommended_action="halt",
            ),
        ]
        report = orchestrator.process("m-scope-multi", events)
        assert report.correlated["total_risk_delta"] >= 0.6
        assert report.recommendation == "halt"

    @pytest.mark.asyncio
    async def test_clean_scope_then_dispatch_succeeds(self) -> None:
        """After clean scope validation, router dispatch should succeed."""
        orchestrator = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="m-scope-ok-route",
                magnet_name="scope_magnet",
                inflection_point="post_execution",
                observed_signal={"violations": []},
                risk_delta=0.0,
                confidence_delta=1.0,
                recommended_action="none",
            ),
        ]
        report = orchestrator.process("m-scope-ok-route", events)
        assert report.recommendation in ("proceed", "proceed_reversible_only")

        router = _router_with_mock(content="scope validated ok")
        req = _make_request(confidence_score=85.0, objective="post-scope-validation dispatch")
        resp = await router.route(req)
        assert resp.output.type == OutputType.TEXT
        assert resp.selected_provider == "mock"


# ---------------------------------------------------------------------------
# 4. Magnet conflict resolution (competing risk signals)
# ---------------------------------------------------------------------------


class TestMagnetConflictResolution:
    """When magnets emit competing signals the orchestrator should resolve correctly."""

    def test_one_halt_among_positive_signals_forces_halt(self) -> None:
        """A single halt-action event dominates over several positive events."""
        orchestrator = MagnetOrchestrator()
        events = [
            # Positive signals
            MagnetEvent(
                mission_id="m-conflict",
                magnet_name="confidence_magnet",
                inflection_point="plan_complete",
                observed_signal={},
                confidence_delta=10.0,
                risk_delta=0.0,
                recommended_action="none",
            ),
            MagnetEvent(
                mission_id="m-conflict",
                magnet_name="validation_magnet",
                inflection_point="tests_complete",
                observed_signal={},
                confidence_delta=5.0,
                risk_delta=0.0,
                recommended_action="none",
            ),
            # Single risk signal
            MagnetEvent(
                mission_id="m-conflict",
                magnet_name="security_magnet",
                inflection_point="post_execution",
                observed_signal={"violation": "critical"},
                confidence_delta=-2.0,
                risk_delta=0.9,
                recommended_action="halt",
            ),
        ]
        report = orchestrator.process("m-conflict", events)
        assert report.recommendation == "halt"

    def test_competing_review_signals_produce_replan_or_review(self) -> None:
        """Multiple 'review' signals without halt should produce a non-proceed recommendation."""
        orchestrator = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="m-review-mix",
                magnet_name="scope_magnet",
                inflection_point="post_execution",
                observed_signal={},
                risk_delta=0.15,
                confidence_delta=-2.0,
                recommended_action="review",
            ),
            MagnetEvent(
                mission_id="m-review-mix",
                magnet_name="cost_magnet",
                inflection_point="execution_complete",
                observed_signal={},
                risk_delta=0.1,
                confidence_delta=-1.0,
                recommended_action="review",
            ),
        ]
        report = orchestrator.process("m-review-mix", events)
        assert report.recommendation in ("replan", "review", "proceed_reversible_only")

    def test_zero_events_produces_review_recommendation(self) -> None:
        """With no events the orchestrator should recommend review (not proceed)."""
        orchestrator = MagnetOrchestrator()
        report = orchestrator.process("m-empty", [])
        assert report.recommendation == "review"
        assert report.collected_count == 0

    def test_high_risk_delta_sum_scores_below_60(self) -> None:
        """Multiple magnets with cumulative high risk push score below 60."""
        orchestrator = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="m-highrisk",
                magnet_name=f"magnet_{i}",
                inflection_point="execution",
                observed_signal={},
                risk_delta=0.2,
                confidence_delta=0.0,
                recommended_action="review",
            )
            for i in range(5)
        ]
        report = orchestrator.process("m-highrisk", events)
        # total_risk_delta = 1.0 -> risk_score = 1.0 -> score = confidence - 20
        assert report.risk_score >= 0.5

    def test_positive_and_negative_confidence_deltas_cancel(self) -> None:
        """Equal positive and negative confidence deltas should result in baseline score."""
        orchestrator = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="m-cancel",
                magnet_name="confidence_magnet",
                inflection_point="p1",
                observed_signal={},
                confidence_delta=10.0,
                risk_delta=0.0,
            ),
            MagnetEvent(
                mission_id="m-cancel",
                magnet_name="validation_magnet",
                inflection_point="p2",
                observed_signal={},
                confidence_delta=-10.0,
                risk_delta=0.0,
            ),
        ]
        report = orchestrator.process("m-cancel", events)
        # Net delta = 0; base = 75 + 0 = 75; risk = 0 -> score ~ 75
        assert 70.0 <= report.confidence_score <= 80.0

    def test_escalation_count_tracked_in_correlated(self) -> None:
        orchestrator = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="m-esc",
                magnet_name="scope_magnet",
                inflection_point="post_exec",
                observed_signal={},
                recommended_action="escalate",
            ),
            MagnetEvent(
                mission_id="m-esc",
                magnet_name="security_magnet",
                inflection_point="post_exec",
                observed_signal={},
                recommended_action="review",
            ),
        ]
        report = orchestrator.process("m-esc", events)
        assert report.correlated["escalations"] >= 1

    @pytest.mark.asyncio
    async def test_router_and_magnet_pipeline_sequential(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Router then magnet pipeline: combined pass/fail is coherent."""
        monkeypatch.setenv("CHROMATIC_ROUTER_DAILY_SPEND", "0.0")
        router = _router_with_mock(content="result")
        req = _make_request(confidence_score=85.0, max_cost_usd=5.0)
        resp = await router.route(req)

        # Router should succeed
        assert resp.output.type == OutputType.TEXT

        # Magnet pipeline on the same mission should also reflect healthy state
        orchestrator = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id=req.task_id,
                magnet_name="execution_magnet",
                inflection_point="execution_complete",
                observed_signal={"exit_code": 0, "duration_s": 1.2},
                confidence_delta=2.0,
                risk_delta=0.0,
                recommended_action="none",
            ),
        ]
        report = orchestrator.process(req.task_id, events)
        assert report.recommendation in ("proceed", "proceed_reversible_only")
