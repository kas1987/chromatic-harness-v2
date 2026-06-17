"""Tests for orchestrator/orchestrator.py — Orchestrator and MissionPacket."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))


# ---------------------------------------------------------------------------
# Lazy import helpers — defer heavy transitive imports until test bodies run
# ---------------------------------------------------------------------------


def _import_orchestrator():
    """Import Orchestrator and MissionPacket with router/magnet stubs in place."""
    # Provide minimal stubs so the module-level imports in orchestrator.py succeed
    # without requiring live provider credentials or filesystem side-effects.
    _ensure_stubs()
    from orchestrator.orchestrator import MissionPacket, Orchestrator

    return Orchestrator, MissionPacket


def _ensure_stubs():
    """Register lightweight stubs for heavy dependencies once per process."""
    stubs = {
        "router": MagicMock(),
        "router.router": MagicMock(),
        "router.observability": MagicMock(),
        "router.contracts": MagicMock(),
        "router.confidence": MagicMock(),
        "scope": MagicMock(),
        "scope.guard": MagicMock(),
        "scope.enforcer": MagicMock(),
        "magnets": MagicMock(),
        "magnets.base_magnet": MagicMock(),
        "magnets.magnet_orchestrator": MagicMock(),
        "memory": MagicMock(),
        "memory.store": MagicMock(),
    }
    for name, stub in stubs.items():
        if name not in sys.modules:
            sys.modules[name] = stub

    # Wire up attribute access that orchestrator.py uses at import time
    import importlib

    # router.contracts enums / dataclasses
    from unittest.mock import MagicMock as MM

    rc = sys.modules["router.contracts"]
    # Only patch attributes when rc is our MagicMock stub.
    # If router.contracts is the real module (already imported by another test),
    # patching it would corrupt RouteConstraints for the rest of the session.
    _rc_is_stub = isinstance(rc, MagicMock)

    class _TaskType:
        PLANNING = "planning"
        CODING = "coding"

        def __init__(self, v):
            self.value = v

    class _PrivacyClass:
        P1 = "P1"

        def __init__(self, v):
            self.value = v

    class _ConfidenceBand:
        HIGH = "high"

        def __init__(self, v):
            self.value = v

    class _RouteConfidence:
        def __init__(self, score=0.0, band=None, reason=""):
            self.score = score
            self.band = band
            self.reason = reason

    class _RouteConstraints:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    class _RouteAudit:
        def __init__(self, caller="unknown", **kw):
            self.caller = caller

    class _RouteInput:
        def __init__(self, **kw):
            pass

    class _RouteRequest:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    if _rc_is_stub:
        rc.TaskType = _TaskType
        rc.PrivacyClass = _PrivacyClass
        rc.RouteConfidence = _RouteConfidence
        rc.RouteConstraints = _RouteConstraints
        rc.RouteAudit = _RouteAudit
        rc.RouteInput = _RouteInput
        rc.RouteRequest = _RouteRequest
        rc.ConfidenceBand = _ConfidenceBand

    # router.confidence.ConfidenceGate
    cg = MagicMock()
    cg.band_from_score.return_value = _ConfidenceBand("high")
    if isinstance(sys.modules.get("router.confidence"), MagicMock):
        sys.modules["router.confidence"].ConfidenceGate = cg

    # magnets.magnet_orchestrator.MagnetOrchestrator
    mag_orch_cls = MagicMock()
    mag_orch_instance = MagicMock()
    mag_orch_instance.registered_magnets.return_value = ["scope_magnet", "security_magnet"]
    mag_orch_cls.return_value = mag_orch_instance
    if isinstance(sys.modules.get("magnets.magnet_orchestrator"), MagicMock):
        sys.modules["magnets.magnet_orchestrator"].MagnetOrchestrator = mag_orch_cls
        sys.modules["magnets.magnet_orchestrator"].MagnetReport = MagicMock

    # scope.guard.DispatchGuard
    dg_cls = MagicMock()
    dg_instance = AsyncMock()
    guarded = MagicMock()
    guarded.mission = {"metadata": {}}
    guarded.scope_baseline = MagicMock(expected_scope="02_RUNTIME/", baseline_count=10)
    guarded.injected_context = {"governance_rules": [{"name": "file_scope_rule"}]}
    guarded.scope_header = "FILE_SCOPE: 02_RUNTIME/"
    dg_instance.guard.return_value = guarded
    dg_cls.return_value = dg_instance
    if isinstance(sys.modules.get("scope.guard"), MagicMock):
        sys.modules["scope.guard"].DispatchGuard = dg_cls

    # router.observability.ObservabilityLogger
    obs_cls = MagicMock()
    obs_instance = MagicMock()
    obs_cls.return_value = obs_instance
    if isinstance(sys.modules.get("router.observability"), MagicMock):
        sys.modules["router.observability"].ObservabilityLogger = obs_cls


# ---------------------------------------------------------------------------
# MissionPacket
# ---------------------------------------------------------------------------


class TestMissionPacket:
    def setup_method(self):
        _ensure_stubs()
        from orchestrator.orchestrator import MissionPacket

        self.MissionPacket = MissionPacket

    def test_fields_stored(self):
        mp = self.MissionPacket(
            mission_id="CHR-MISSION-ABCD1234",
            objective="refactor auth module",
            agent_role="worker",
            autonomy_level="L1",
            confidence_required=80.0,
            allowed_tools=["filesystem.read"],
            stop_conditions=["scope_unclear"],
            required_outputs=["task_result"],
        )
        assert mp.mission_id == "CHR-MISSION-ABCD1234"
        assert mp.objective == "refactor auth module"
        assert mp.agent_role == "worker"
        assert mp.autonomy_level == "L1"
        assert mp.confidence_required == 80.0
        assert mp.allowed_tools == ["filesystem.read"]
        assert mp.stop_conditions == ["scope_unclear"]
        assert mp.required_outputs == ["task_result"]

    def test_metadata_defaults_empty_dict(self):
        mp = self.MissionPacket(
            mission_id="m1",
            objective="x",
            agent_role="r",
            autonomy_level="L1",
            confidence_required=75.0,
            allowed_tools=[],
            stop_conditions=[],
            required_outputs=[],
        )
        assert mp.metadata == {}

    def test_metadata_accepts_dict(self):
        mp = self.MissionPacket(
            mission_id="m1",
            objective="x",
            agent_role="r",
            autonomy_level="L1",
            confidence_required=75.0,
            allowed_tools=[],
            stop_conditions=[],
            required_outputs=[],
            metadata={"bead_id": "bd-001"},
        )
        assert mp.metadata["bead_id"] == "bd-001"


# ---------------------------------------------------------------------------
# Orchestrator.create_mission
# ---------------------------------------------------------------------------


class TestOrchestratorCreateMission:
    def setup_method(self):
        Orchestrator, _ = _import_orchestrator()
        self.orch = Orchestrator()

    def test_returns_mission_packet(self):
        from orchestrator.orchestrator import MissionPacket

        mp = self.orch.create_mission("write new tests")
        assert isinstance(mp, MissionPacket)

    def test_mission_id_format(self):
        mp = self.orch.create_mission("any intent")
        assert mp.mission_id.startswith("CHR-MISSION-")

    def test_mission_id_unique(self):
        ids = {self.orch.create_mission("x").mission_id for _ in range(10)}
        assert len(ids) == 10

    def test_objective_set_from_intent(self):
        mp = self.orch.create_mission("implement feature X")
        assert mp.objective == "implement feature X"

    def test_agent_role_is_agent_lead(self):
        mp = self.orch.create_mission("anything")
        assert mp.agent_role == "agent_lead"

    def test_autonomy_level_l1(self):
        mp = self.orch.create_mission("anything")
        assert mp.autonomy_level == "L1"

    def test_confidence_required_75(self):
        mp = self.orch.create_mission("anything")
        assert mp.confidence_required == 75

    def test_allowed_tools_contains_filesystem_read(self):
        mp = self.orch.create_mission("anything")
        assert "filesystem.read" in mp.allowed_tools

    def test_stop_conditions_non_empty(self):
        mp = self.orch.create_mission("anything")
        assert len(mp.stop_conditions) > 0

    def test_required_outputs_contains_agent_lead_report(self):
        mp = self.orch.create_mission("anything")
        assert "agent_lead_report" in mp.required_outputs

    def test_required_outputs_contains_next_bead(self):
        mp = self.orch.create_mission("anything")
        assert "next_bead" in mp.required_outputs


# ---------------------------------------------------------------------------
# Orchestrator.create_mission_from_task
# ---------------------------------------------------------------------------


class TestOrchestratorCreateMissionFromTask:
    def setup_method(self):
        Orchestrator, _ = _import_orchestrator()
        self.orch = Orchestrator()

    def _task(self, **kw):
        base = {
            "title": "Implement auth module",
            "confidence_required": 80.0,
            "role": "worker",
            "tool_budget": 10,
        }
        base.update(kw)
        return base

    def test_objective_from_title(self):
        mp = self.orch.create_mission_from_task(self._task())
        assert mp.objective == "Implement auth module"

    def test_objective_fallback_to_objective_key(self):
        task = {"objective": "fallback objective", "confidence_required": 75.0}
        mp = self.orch.create_mission_from_task(task)
        assert mp.objective == "fallback objective"

    def test_confidence_required_from_task(self):
        mp = self.orch.create_mission_from_task(self._task(confidence_required=85.0))
        assert mp.confidence_required == 85.0

    def test_confidence_score_fallback_key(self):
        task = {"title": "t", "confidence_score": 70.0}
        mp = self.orch.create_mission_from_task(task)
        assert mp.confidence_required == 70.0

    def test_confidence_defaults_to_75(self):
        task = {"title": "t"}
        mp = self.orch.create_mission_from_task(task)
        assert mp.confidence_required == 75.0

    def test_role_from_task(self):
        mp = self.orch.create_mission_from_task(self._task(role="reviewer"))
        assert mp.agent_role == "reviewer"

    def test_role_defaults_to_worker(self):
        task = {"title": "t"}
        mp = self.orch.create_mission_from_task(task)
        assert mp.agent_role == "worker"

    def test_autonomy_l2_when_tool_budget_over_20(self):
        mp = self.orch.create_mission_from_task(self._task(tool_budget=21))
        assert mp.autonomy_level == "L2"

    def test_autonomy_l1_when_tool_budget_at_or_below_20(self):
        mp = self.orch.create_mission_from_task(self._task(tool_budget=20))
        assert mp.autonomy_level == "L1"

    def test_autonomy_l1_when_tool_budget_zero(self):
        mp = self.orch.create_mission_from_task(self._task(tool_budget=0))
        assert mp.autonomy_level == "L1"

    def test_allowed_files_adds_write_tool(self):
        mp = self.orch.create_mission_from_task(self._task(allowed_files=["src/main.py"]))
        assert "filesystem.write" in mp.allowed_tools

    def test_no_allowed_files_no_write_tool(self):
        mp = self.orch.create_mission_from_task(self._task(allowed_files=[]))
        assert "filesystem.write" not in mp.allowed_tools

    def test_required_outputs(self):
        mp = self.orch.create_mission_from_task(self._task())
        assert "task_result" in mp.required_outputs
        assert "verifier_report" in mp.required_outputs

    def test_metadata_task_id(self):
        mp = self.orch.create_mission_from_task(self._task(task_id="TASK-001"))
        assert mp.metadata["task_id"] == "TASK-001"

    def test_metadata_bead_id(self):
        mp = self.orch.create_mission_from_task(self._task(bead_id="bd-42"))
        assert mp.metadata["bead_id"] == "bd-42"

    def test_metadata_allowed_files_stored(self):
        files = ["src/a.py", "src/b.py"]
        mp = self.orch.create_mission_from_task(self._task(allowed_files=files))
        assert mp.metadata["allowed_files"] == files

    def test_custom_stop_conditions(self):
        mp = self.orch.create_mission_from_task(self._task(stop_conditions=["custom_stop"]))
        assert mp.stop_conditions == ["custom_stop"]

    def test_default_stop_conditions_non_empty(self):
        task = {"title": "t"}
        mp = self.orch.create_mission_from_task(task)
        assert len(mp.stop_conditions) > 0

    def test_mission_id_unique_per_call(self):
        ids = {self.orch.create_mission_from_task(self._task()).mission_id for _ in range(5)}
        assert len(ids) == 5


# ---------------------------------------------------------------------------
# Orchestrator.attach_magnets
# ---------------------------------------------------------------------------


class TestOrchestratorAttachMagnets:
    def setup_method(self):
        Orchestrator, _ = _import_orchestrator()
        self.orch = Orchestrator()

    def test_returns_list(self):
        from orchestrator.orchestrator import MissionPacket

        mp = MissionPacket(
            mission_id="m1",
            objective="x",
            agent_role="r",
            autonomy_level="L1",
            confidence_required=75.0,
            allowed_tools=[],
            stop_conditions=[],
            required_outputs=[],
        )
        result = self.orch.attach_magnets(mp)
        assert isinstance(result, list)

    def test_delegates_to_magnet_orchestrator(self):
        from orchestrator.orchestrator import MissionPacket

        mp = MissionPacket(
            mission_id="m1",
            objective="x",
            agent_role="r",
            autonomy_level="L1",
            confidence_required=75.0,
            allowed_tools=[],
            stop_conditions=[],
            required_outputs=[],
        )
        result = self.orch.attach_magnets(mp)
        # Stub returns ["scope_magnet", "security_magnet"]
        assert "scope_magnet" in result


# ---------------------------------------------------------------------------
# Orchestrator.dispatch
# ---------------------------------------------------------------------------


class TestOrchestratorDispatch:
    def setup_method(self):
        Orchestrator, _ = _import_orchestrator()
        self.orch = Orchestrator()

    def _mp(self, **kw):
        from orchestrator.orchestrator import MissionPacket

        defaults = dict(
            mission_id="CHR-MISSION-TESTTEST",
            objective="test objective",
            agent_role="worker",
            autonomy_level="L1",
            confidence_required=75.0,
            allowed_tools=["filesystem.read"],
            stop_conditions=["scope_unclear"],
            required_outputs=["task_result"],
        )
        defaults.update(kw)
        return MissionPacket(**defaults)

    def test_returns_dict(self):
        result = self.orch.dispatch(self._mp())
        assert isinstance(result, dict)

    def test_result_contains_mission_id(self):
        mp = self._mp()
        result = self.orch.dispatch(mp)
        assert result["mission_id"] == mp.mission_id

    def test_result_status_ready_for_runtime(self):
        result = self.orch.dispatch(self._mp())
        assert result["status"] == "ready_for_runtime"

    def test_result_contains_magnets_key(self):
        result = self.orch.dispatch(self._mp())
        assert "magnets" in result

    def test_magnets_is_list(self):
        result = self.orch.dispatch(self._mp())
        assert isinstance(result["magnets"], list)


# ---------------------------------------------------------------------------
# Orchestrator.guard_and_inject (async)
# ---------------------------------------------------------------------------


class TestOrchestratorGuardAndInject:
    def _mp(self):
        from orchestrator.orchestrator import MissionPacket

        return MissionPacket(
            mission_id="CHR-MISSION-GUARD001",
            objective="review PR",
            agent_role="worker",
            autonomy_level="L1",
            confidence_required=75.0,
            allowed_tools=[],
            stop_conditions=[],
            required_outputs=[],
        )

    @pytest.mark.asyncio
    async def test_returns_dict_with_expected_keys(self):
        from orchestrator.orchestrator import Orchestrator

        orch = Orchestrator()
        result = await orch.guard_and_inject(self._mp(), file_scope="02_RUNTIME/")
        assert "mission_id" in result
        assert "status" in result
        assert "scope_baseline" in result
        assert "injected_rules" in result
        assert "scope_header_present" in result

    @pytest.mark.asyncio
    async def test_status_is_guarded_and_ready(self):
        from orchestrator.orchestrator import Orchestrator

        orch = Orchestrator()
        result = await orch.guard_and_inject(self._mp())
        assert result["status"] == "guarded_and_ready"

    @pytest.mark.asyncio
    async def test_mission_id_preserved(self):
        from orchestrator.orchestrator import Orchestrator

        orch = Orchestrator()
        mp = self._mp()
        result = await orch.guard_and_inject(mp)
        assert result["mission_id"] == mp.mission_id

    @pytest.mark.asyncio
    async def test_scope_header_present_when_scope_provided(self):
        from orchestrator.orchestrator import Orchestrator

        orch = Orchestrator()
        result = await orch.guard_and_inject(self._mp(), file_scope="02_RUNTIME/")
        # The stub sets scope_header to a non-empty string
        assert result["scope_header_present"] is True

    @pytest.mark.asyncio
    async def test_injected_rules_from_governance(self):
        from orchestrator.orchestrator import Orchestrator

        orch = Orchestrator()
        result = await orch.guard_and_inject(self._mp())
        assert isinstance(result["injected_rules"], list)


# ---------------------------------------------------------------------------
# Orchestrator.verify_scope_after_work (async)
# ---------------------------------------------------------------------------


class TestOrchestratorVerifyScopeAfterWork:
    def _mp(self):
        from orchestrator.orchestrator import MissionPacket

        return MissionPacket(
            mission_id="CHR-MISSION-VERIFY01",
            objective="write tests",
            agent_role="worker",
            autonomy_level="L1",
            confidence_required=75.0,
            allowed_tools=[],
            stop_conditions=[],
            required_outputs=[],
        )

    @pytest.mark.asyncio
    async def test_no_scope_declared_returns_passed(self):
        from orchestrator.orchestrator import Orchestrator

        orch = Orchestrator()
        result = await orch.verify_scope_after_work(self._mp(), baseline={})
        assert result["passed"] is True
        assert result["reason"] == "no_scope_declared"

    @pytest.mark.asyncio
    async def test_no_expected_scope_key_returns_passed(self):
        from orchestrator.orchestrator import Orchestrator

        orch = Orchestrator()
        result = await orch.verify_scope_after_work(self._mp(), baseline={"expected_scope": ""})
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_with_scope_calls_enforcer(self):
        from orchestrator.orchestrator import Orchestrator

        orch = Orchestrator()

        mock_result = MagicMock(
            passed=True,
            violations=[],
            new_files=[],
            modified_outside=[],
        )
        mock_enforcer = AsyncMock()
        mock_enforcer.enforce_and_log.return_value = mock_result

        with (
            patch("scope.enforcer.ScopeEnforcer", return_value=mock_enforcer),
            patch("scope.enforcer.ScopeBaseline", return_value=MagicMock()),
        ):
            result = await orch.verify_scope_after_work(
                self._mp(),
                baseline={"expected_scope": "02_RUNTIME/", "baseline_count": 5},
            )

        assert result["passed"] is True
        assert "violations" in result
        assert "new_files_outside_scope" in result
        assert "modified_outside_scope" in result


# ---------------------------------------------------------------------------
# Orchestrator.complete_mission
# ---------------------------------------------------------------------------


class TestOrchestratorCompleteMission:
    def _mp(self):
        from orchestrator.orchestrator import MissionPacket

        return MissionPacket(
            mission_id="CHR-MISSION-DONE0001",
            objective="done task",
            agent_role="worker",
            autonomy_level="L1",
            confidence_required=80.0,
            allowed_tools=[],
            stop_conditions=[],
            required_outputs=[],
        )

    def test_complete_mission_does_not_raise(self):
        from orchestrator.orchestrator import Orchestrator

        orch = Orchestrator()
        # Should complete without error — the stub ObservabilityLogger absorbs the call
        orch.complete_mission(
            self._mp(),
            model="claude-sonnet-4-5",
            role="worker",
            files_touched=["src/main.py"],
            result="task_result",
            validation="tests_passed",
            next_task="CHR-NEXT",
            tools_used=5,
        )

    def test_complete_mission_with_minimal_args(self):
        from orchestrator.orchestrator import Orchestrator

        orch = Orchestrator()
        orch.complete_mission(
            self._mp(),
            model="claude-haiku",
            role="reviewer",
            files_touched=[],
            result="review_complete",
        )


# ---------------------------------------------------------------------------
# Orchestrator state machine transitions (create → dispatch lifecycle)
# ---------------------------------------------------------------------------


class TestOrchestratorStateMachine:
    """Verify the create → attach → dispatch lifecycle produces consistent state."""

    def setup_method(self):
        Orchestrator, _ = _import_orchestrator()
        self.orch = Orchestrator()

    def test_create_then_dispatch_preserves_mission_id(self):
        mp = self.orch.create_mission("build feature Y")
        result = self.orch.dispatch(mp)
        assert result["mission_id"] == mp.mission_id

    def test_create_from_task_then_dispatch(self):
        mp = self.orch.create_mission_from_task({"title": "fix bug", "tool_budget": 5})
        result = self.orch.dispatch(mp)
        assert result["status"] == "ready_for_runtime"

    def test_dispatch_twice_same_mission_consistent(self):
        mp = self.orch.create_mission("run twice")
        r1 = self.orch.dispatch(mp)
        r2 = self.orch.dispatch(mp)
        assert r1["mission_id"] == r2["mission_id"]
        assert r1["status"] == r2["status"]

    def test_high_tool_budget_produces_l2(self):
        mp = self.orch.create_mission_from_task({"title": "big task", "tool_budget": 50})
        assert mp.autonomy_level == "L2"

    def test_stop_conditions_preserved_through_dispatch(self):
        mp = self.orch.create_mission_from_task({"title": "t", "stop_conditions": ["custom_halt"]})
        assert "custom_halt" in mp.stop_conditions

    @pytest.mark.asyncio
    async def test_full_lifecycle_create_guard_dispatch(self):
        from orchestrator.orchestrator import Orchestrator

        orch = Orchestrator()
        mp = orch.create_mission("full lifecycle test")
        guard_result = await orch.guard_and_inject(mp, file_scope="")
        dispatch_result = orch.dispatch(mp)
        assert guard_result["mission_id"] == dispatch_result["mission_id"]
        assert dispatch_result["status"] == "ready_for_runtime"
