"""Tests for 02_RUNTIME/orchestrator/orchestrator.py — batch 1."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

_RUNTIME = Path(__file__).resolve().parent.parent / "02_RUNTIME"
_MODULE_PATH = _RUNTIME / "orchestrator" / "orchestrator.py"


def _load_module(monkeypatch) -> types.ModuleType:
    """Load orchestrator.orchestrator via importlib, stubbing heavy deps."""
    # Stub scope.guard
    guard_mod = types.ModuleType("scope.guard")

    class _FakeGuardResult:
        def __init__(self):
            self.mission = {"metadata": {}}
            self.scope_baseline = None
            self.injected_context = {"governance_rules": []}
            self.scope_header = ""

    class _FakeDispatchGuard:
        async def guard(self, mission, *, file_scope="", agent_id=""):
            return _FakeGuardResult()

    guard_mod.DispatchGuard = _FakeDispatchGuard
    monkeypatch.setitem(sys.modules, "scope.guard", guard_mod)
    monkeypatch.setitem(sys.modules, "scope", types.ModuleType("scope"))

    # Stub magnets
    base_mag = types.ModuleType("magnets.base_magnet")
    base_mag.MagnetEvent = object
    monkeypatch.setitem(sys.modules, "magnets.base_magnet", base_mag)

    mag_orch = types.ModuleType("magnets.magnet_orchestrator")

    class _FakeMagnetOrchestrator:
        def registered_magnets(self):
            return ["quota", "context", "discipline"]

        def process(self, mission_id, events):
            return {"mission_id": mission_id, "events_processed": len(events)}

    mag_orch.MagnetOrchestrator = _FakeMagnetOrchestrator
    monkeypatch.setitem(sys.modules, "magnets.magnet_orchestrator", mag_orch)
    monkeypatch.setitem(sys.modules, "magnets", types.ModuleType("magnets"))

    spec = importlib.util.spec_from_file_location("orchestrator.orchestrator", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["orchestrator.orchestrator"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def orch_mod(monkeypatch):
    return _load_module(monkeypatch)


@pytest.fixture()
def orchestrator(orch_mod):
    return orch_mod.Orchestrator()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOrchestrator:
    def test_import_clean(self, orch_mod):
        """Module imports without error and exposes Orchestrator + MissionPacket."""
        assert hasattr(orch_mod, "Orchestrator")
        assert hasattr(orch_mod, "MissionPacket")

    def test_create_mission_happy_path(self, orchestrator, orch_mod):
        """create_mission returns a MissionPacket with a unique CHR-MISSION- id."""
        mission = orchestrator.create_mission("implement feature X")
        assert isinstance(mission, orch_mod.MissionPacket)
        assert mission.mission_id.startswith("CHR-MISSION-")
        assert mission.objective == "implement feature X"
        assert mission.agent_role == "agent_lead"
        assert mission.confidence_required == 75

    def test_create_mission_from_task_happy_path(self, orchestrator, orch_mod):
        """create_mission_from_task maps task dict fields correctly."""
        task = {
            "title": "refactor router",
            "confidence_required": 90,
            "role": "refactor_worker",
            "tool_budget": 30,
            "allowed_files": ["router/router.py"],
            "task_id": "T-001",
            "assigned_model": "claude-sonnet",
        }
        mission = orchestrator.create_mission_from_task(task)
        assert mission.objective == "refactor router"
        assert mission.confidence_required == 90
        assert mission.agent_role == "refactor_worker"
        assert mission.autonomy_level == "L2"  # tool_budget > 20
        assert "filesystem.write" in mission.allowed_tools
        assert mission.metadata["task_id"] == "T-001"

    def test_create_mission_from_task_l1_autonomy(self, orchestrator):
        """Tool budget <= 20 results in L1 autonomy level."""
        task = {"title": "small task", "tool_budget": 10}
        mission = orchestrator.create_mission_from_task(task)
        assert mission.autonomy_level == "L1"

    def test_create_mission_from_task_empty_allowed_files(self, orchestrator):
        """No allowed_files means filesystem.write is not granted."""
        task = {"title": "read-only task", "allowed_files": []}
        mission = orchestrator.create_mission_from_task(task)
        assert "filesystem.write" not in mission.allowed_tools
        assert "filesystem.read" in mission.allowed_tools

    def test_attach_magnets_returns_list(self, orchestrator):
        """attach_magnets returns a non-empty list from MagnetOrchestrator."""
        mission = orchestrator.create_mission("test")
        magnets = orchestrator.attach_magnets(mission)
        assert isinstance(magnets, list)
        assert len(magnets) > 0

    def test_dispatch_happy_path(self, orchestrator):
        """dispatch returns ready_for_runtime status with magnets list."""
        mission = orchestrator.create_mission("dispatch test")
        result = orchestrator.dispatch(mission)
        assert result["status"] == "ready_for_runtime"
        assert result["mission_id"] == mission.mission_id
        assert isinstance(result["magnets"], list)

    def test_mission_packet_confidence_score_alias(self, orch_mod):
        """confidence_score property mirrors confidence_required."""
        mp = orch_mod.MissionPacket(
            mission_id="CHR-MISSION-TEST",
            objective="test",
            agent_role="agent_lead",
            autonomy_level="L1",
            confidence_required=82,
            allowed_tools=[],
            stop_conditions=[],
            required_outputs=[],
        )
        assert mp.confidence_score == 82
        assert mp.confidence_score == mp.confidence_required

    def test_mission_id_uniqueness(self, orchestrator):
        """Each create_mission call produces a different mission_id."""
        ids = {orchestrator.create_mission(f"task {i}").mission_id for i in range(10)}
        assert len(ids) == 10

    def test_create_mission_from_task_default_confidence(self, orchestrator):
        """Missing confidence_required defaults to 75."""
        task = {"title": "default conf"}
        mission = orchestrator.create_mission_from_task(task)
        assert mission.confidence_required == 75

    def test_create_mission_from_task_accepts_confidence_score_key(self, orchestrator):
        """create_mission_from_task also accepts confidence_score as the dict key."""
        task = {"title": "alt key", "confidence_score": 88}
        mission = orchestrator.create_mission_from_task(task)
        assert mission.confidence_required == 88

    @pytest.mark.asyncio
    async def test_guard_and_inject_returns_dict(self, orchestrator):
        """guard_and_inject returns a well-formed status dict."""
        mission = orchestrator.create_mission("guard test")
        result = await orchestrator.guard_and_inject(mission, file_scope="src/")
        assert result["status"] == "guarded_and_ready"
        assert result["mission_id"] == mission.mission_id
        assert "scope_baseline" in result
        assert "injected_rules" in result

    def test_fail_open_missing_task_keys(self, orchestrator):
        """create_mission_from_task handles completely empty task dict without raising."""
        mission = orchestrator.create_mission_from_task({})
        assert mission.mission_id.startswith("CHR-MISSION-")
        assert mission.objective == ""

    def test_boundary_confidence_zero(self, orchestrator):
        """Zero confidence_required is accepted as-is (boundary)."""
        task = {"title": "zero conf", "confidence_required": 0}
        mission = orchestrator.create_mission_from_task(task)
        assert mission.confidence_required == 0

    def test_boundary_confidence_100(self, orchestrator):
        """Max confidence_required=100 is accepted (boundary)."""
        task = {"title": "max conf", "confidence_required": 100}
        mission = orchestrator.create_mission_from_task(task)
        assert mission.confidence_required == 100
