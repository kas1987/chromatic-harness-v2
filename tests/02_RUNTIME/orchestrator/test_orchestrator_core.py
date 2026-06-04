"""Comprehensive tests for orchestrator/orchestrator.py — synthesize_mission and related methods.

# DEFICIENCIES NOTED
#
# 1. synthesize_mission uses importlib.util.spec_from_file_location to load agent_lead.py by
#    absolute filesystem path (_HERE / "agent_lead.py") and then unconditionally registers it
#    under sys.modules["agent_lead"].  This means patching "orchestrator.orchestrator.AgentLead"
#    at the module level doesn't work — callers must intercept either the importlib machinery
#    itself or mock sys.modules["agent_lead"] before the call.  This is a significant testability
#    gap: the side-effectful module injection (sys.modules["agent_lead"] = mod) pollutes the
#    global module registry and can break test isolation between runs.
#
# 2. session_compact.write_handoff is called inside AgentLead.run (wrapped in a bare except).
#    It runs git subprocesses (branch, log) against the live repo filesystem.  The silent except
#    prevents hard failures in tests, but it adds non-deterministic I/O to every synthesize_mission
#    call.  There is no interface seam for injecting a no-op session-compact writer.
#
# 3. complete_mission builds inner _Fake* classes inline on every call to create minimal stubs
#    compatible with ObservabilityLogger._log_agent_run.  This approach requires _log_agent_run to
#    open a real file (AGENT_RUN_LOG.jsonl) and write to disk.  There is no in-memory or no-op
#    logging mode, making unit tests either write to the project log or require patch at a deep
#    internal method.
#
# 4. route_to_provider sets the module-level ChromaticRouter global in-place via a conditional
#    import (if ChromaticRouter is None: from router.router import …).  Once set by a test that
#    runs the live import, subsequent tests cannot re-inject a stub without patching the module
#    global directly.  The existing test file handles this correctly with
#    patch("orchestrator.orchestrator.ChromaticRouter"), but the pattern is fragile across test
#    ordering.
#
# 5. verify_scope_after_work performs a deferred "from scope.enforcer import …" inside the method
#    body.  Because scope.enforcer is already stubbed as a MagicMock in sys.modules by _ensure_stubs,
#    the "from … import ScopeEnforcer, ScopeBaseline" will silently resolve to MagicMock attributes.
#    This means the real ScopeEnforcer is never exercised via Orchestrator in tests unless the stub
#    is removed before the call — a non-obvious footgun.
#
# 6. MissionPacket uses a mutable default for metadata (field(default_factory=dict)) which is
#    correct, but metadata is mutated in-place by guard_and_inject via mission.metadata.update().
#    Tests that reuse the same MissionPacket instance across guard_and_inject calls will see
#    accumulated metadata state without any documented contract about idempotency.
#
# 7. The autonomy_level boundary condition (tool_budget > 20 → L2) uses strict greater-than,
#    so tool_budget == 20 stays at L1.  This boundary is not documented in a docstring or schema;
#    it is easy to introduce an off-by-one regression.
#
# 8. IMPORT SHADOW BUG (infrastructure): tests/02_RUNTIME/orchestrator/__init__.py creates a
#    Python package named "orchestrator" that shadows the runtime namespace package at
#    02_RUNTIME/orchestrator/.  Because tests/02_RUNTIME/orchestrator appears first in sys.path,
#    "from orchestrator.orchestrator import ..." always resolves to the test package (which has
#    no orchestrator.py submodule), causing ModuleNotFoundError.  This file works around the
#    problem by loading the source module via importlib.util.spec_from_file_location with the
#    unique alias "orchestrator_core_under_test", mirroring the approach used in
#    test_confidence_engine.py.  The root cause is the __init__.py in the test directory; removing
#    it or renaming the test package would fix the issue for all orchestrator tests.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# sys.path bootstrap — must run before any local imports
# ---------------------------------------------------------------------------

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
_ORCH_PY = _RUNTIME / "orchestrator" / "orchestrator.py"

if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))


# ---------------------------------------------------------------------------
# Module-level stub injection — must happen BEFORE loading orchestrator.py
# ---------------------------------------------------------------------------
#
# orchestrator.py does top-level "from scope.guard import DispatchGuard" and
# "from magnets.base_magnet import MagnetEvent" at import time.  Those modules
# transitively depend on aiosqlite and other packages that are not installed in
# the test environment.  We therefore stub them in sys.modules before the first
# spec_from_file_location call.
#
# We CANNOT use setdefault for modules that are already registered (from a previous
# test run in the same process) because that would overwrite a real module with a
# MagicMock.  The guards below replicate the pattern from test_orchestrator_engine.py.


def _ensure_stubs() -> None:
    """Idempotently register stubs for all heavy dependencies of orchestrator.py."""

    class _ConfidenceBand:
        VERY_HIGH = "very_high"
        HIGH = "high"
        MEDIUM = "medium"
        LOW = "low"
        BLOCKED = "blocked"

        def __init__(self, v: str) -> None:
            self.value = v

    class _TaskType:
        PLANNING = "planning"
        CODING = "coding"

        def __init__(self, v: str) -> None:
            self.value = v

    class _PrivacyClass:
        P1 = "P1"

        def __init__(self, v: str) -> None:
            self.value = v

    class _RouteInput:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    class _RouteConstraints:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    class _RouteRequest:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    class _RouteConfidence:
        def __init__(self, score: float = 0.0, band=None, reason: str = "") -> None:
            self.score = score
            self.band = band
            self.reason = reason

    class _RouteAudit:
        def __init__(self, caller: str = "unknown", **kw) -> None:
            self.caller = caller

    heavy = {
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
    for name, stub in heavy.items():
        sys.modules.setdefault(name, stub)

    # router.contracts — wire up only when our stub is the registered module
    rc = sys.modules["router.contracts"]
    if isinstance(rc, MagicMock):
        rc.TaskType = _TaskType
        rc.PrivacyClass = _PrivacyClass
        rc.RouteInput = _RouteInput
        rc.RouteConstraints = _RouteConstraints
        rc.RouteRequest = _RouteRequest
        rc.ConfidenceBand = _ConfidenceBand
        rc.RouteConfidence = _RouteConfidence
        rc.RouteAudit = _RouteAudit

    # router.confidence.ConfidenceGate
    if isinstance(sys.modules.get("router.confidence"), MagicMock):
        cg = MagicMock()
        cg.band_from_score.return_value = _ConfidenceBand("high")
        sys.modules["router.confidence"].ConfidenceGate = cg

    # magnets.base_magnet.MagnetEvent
    if isinstance(sys.modules.get("magnets.base_magnet"), MagicMock):
        sys.modules["magnets.base_magnet"].MagnetEvent = MagicMock

    # magnets.magnet_orchestrator.MagnetOrchestrator + MagnetReport
    if isinstance(sys.modules.get("magnets.magnet_orchestrator"), MagicMock):
        mag_orch_cls = MagicMock()
        mag_inst = MagicMock()
        mag_inst.registered_magnets.return_value = ["scope_magnet", "security_magnet"]
        mag_orch_cls.return_value = mag_inst
        sys.modules["magnets.magnet_orchestrator"].MagnetOrchestrator = mag_orch_cls
        sys.modules["magnets.magnet_orchestrator"].MagnetReport = MagicMock

    # scope.guard.DispatchGuard
    if isinstance(sys.modules.get("scope.guard"), MagicMock):
        dg_cls = MagicMock()
        dg_inst = AsyncMock()
        guarded = MagicMock()
        guarded.mission = {"metadata": {}}
        guarded.scope_baseline = MagicMock(expected_scope="02_RUNTIME/", baseline_count=10)
        guarded.injected_context = {"governance_rules": [{"name": "file_scope_rule"}]}
        guarded.scope_header = "FILE_SCOPE: 02_RUNTIME/"
        dg_inst.guard.return_value = guarded
        dg_cls.return_value = dg_inst
        sys.modules["scope.guard"].DispatchGuard = dg_cls

    # router.observability.ObservabilityLogger
    if isinstance(sys.modules.get("router.observability"), MagicMock):
        obs_cls = MagicMock()
        obs_inst = MagicMock()
        obs_cls.return_value = obs_inst
        sys.modules["router.observability"].ObservabilityLogger = obs_cls


# Run stubs at module import time so that _load_orch_module() below succeeds.
_ensure_stubs()


# ---------------------------------------------------------------------------
# Load orchestrator.py by file path (avoids the package-name shadow bug)
# ---------------------------------------------------------------------------

_ORCH_MODULE_ALIAS = "orchestrator_core_under_test"


def _load_orch_module():
    """Load orchestrator.py into sys.modules under a unique alias and return it."""
    if _ORCH_MODULE_ALIAS in sys.modules:
        return sys.modules[_ORCH_MODULE_ALIAS]
    _ensure_stubs()
    spec = importlib.util.spec_from_file_location(_ORCH_MODULE_ALIAS, _ORCH_PY)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[_ORCH_MODULE_ALIAS] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Load once at module import time.
_orch_mod = _load_orch_module()
Orchestrator = _orch_mod.Orchestrator
MissionPacket = _orch_mod.MissionPacket


def _make_mission(**overrides):
    """Factory: return a MissionPacket with sensible defaults, overriding as needed."""
    defaults = dict(
        mission_id="CHR-MISSION-CORE0001",
        objective="test the system",
        agent_role="worker",
        autonomy_level="L1",
        confidence_required=75.0,
        allowed_tools=["filesystem.read"],
        stop_conditions=["scope_unclear", "security_risk_detected"],
        required_outputs=["task_result"],
    )
    defaults.update(overrides)
    return MissionPacket(**defaults)


def _build_magnet_report_stub(
    *,
    score=80.0,
    confidence_score=80.0,
    risk_score=0.1,
    recommendation="proceed_reversible_only",
    feedback=None,
    collected_count=3,
    correlated=None,
):
    """Build a minimal MagnetReport-like stub for use in synthesize_mission tests."""
    report = MagicMock()
    report.score = score
    report.confidence_score = confidence_score
    report.risk_score = risk_score
    report.recommendation = recommendation
    report.feedback = feedback if feedback is not None else ["All signals nominal."]
    report.collected_count = collected_count
    report.normalized = []
    report.correlated = (
        correlated
        if correlated is not None
        else {
            "magnets_seen": ["scope_magnet"],
            "inflection_points": ["pre_dispatch"],
            "total_risk_delta": 0.1,
            "total_confidence_delta": 5.0,
            "halt_actions": 0,
            "escalations": 0,
            "event_count": collected_count,
        }
    )
    report.gold_artifact = {"mission_id": "CHR-MISSION-CORE0001", "score": score}
    return report


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _setup_stubs():
    """Ensure stubs are in place for every test in this module."""
    _ensure_stubs()
    yield


@pytest.fixture()
def orch():
    return Orchestrator()


@pytest.fixture()
def mission():
    return _make_mission()


# ---------------------------------------------------------------------------
# synthesize_mission — core focus of this file
# ---------------------------------------------------------------------------


class TestSynthesizeMission:
    """Tests for Orchestrator.synthesize_mission, the main pipeline entry point."""

    def _make_agent_lead_output(self, *, decision="proceed_reversible_only", score=80.0):
        """Build a minimal AgentLeadOutput-like stub."""
        out = MagicMock()
        out.decision = decision
        out.composite_score = score
        out.final_report = {
            "executive_summary": f"Mission scored {score}/100 with decision '{decision}'.",
            "objective": "test objective",
            "synthesis": {},
            "evaluation": {},
            "recommendation": {"decision": decision, "rationale": ["ok"]},
            "achievements": [],
            "findings": [],
        }
        out.pr_package = {"title": "[Agent Lead] test", "ready_for_review": True}
        out.next_steps = {"decision": decision, "actions": ["proceed"], "priority": "p2"}
        out.audit_log = {"mission_id": "CHR-MISSION-CORE0001", "event_count": 2}
        out.handoff_prep = {"directive_summary": "done", "decision": decision}
        out.suggested_bead = None
        return out

    def _patch_synthesize(self, orch_instance, decision="proceed_reversible_only", score=80.0):
        """Context manager: patches importlib, MagnetOrchestrator, and AgentLead."""
        import importlib

        fake_output = self._make_agent_lead_output(decision=decision, score=score)
        fake_report = _build_magnet_report_stub(score=score, recommendation=decision)

        # Stub MagnetOrchestrator instance
        fake_mag_orch = MagicMock()
        fake_mag_orch.process.return_value = fake_report

        # Stub AgentLead class
        fake_agent_lead_cls = MagicMock()
        fake_agent_lead_instance = MagicMock()
        fake_agent_lead_instance.run.return_value = fake_output
        fake_agent_lead_cls.return_value = fake_agent_lead_instance

        # Stub agent_lead module
        fake_agent_lead_mod = types.ModuleType("agent_lead")
        fake_agent_lead_mod.AgentLead = fake_agent_lead_cls

        # Stub spec + loader
        fake_spec = MagicMock()
        fake_spec.loader = MagicMock()

        def fake_exec_module(mod):
            mod.AgentLead = fake_agent_lead_cls

        fake_spec.loader.exec_module.side_effect = fake_exec_module

        return (
            patch("importlib.util.spec_from_file_location", return_value=fake_spec),
            patch("importlib.util.module_from_spec", return_value=fake_agent_lead_mod),
            patch(
                "orchestrator_core_under_test.MagnetOrchestrator",
                return_value=fake_mag_orch,
            ),
            fake_mag_orch,
            fake_agent_lead_instance,
            fake_output,
        )

    def test_returns_agent_lead_output(self, orch, mission):
        """synthesize_mission must return the value produced by AgentLead.run."""
        (
            p_spec,
            p_mod,
            p_mag,
            fake_mag_orch,
            fake_lead_instance,
            fake_output,
        ) = self._patch_synthesize(orch)

        with p_spec, p_mod, p_mag:
            result = orch.synthesize_mission(mission, [])

        assert result is fake_output

    def test_passes_mission_id_to_magnet_orchestrator(self, orch, mission):
        """MagnetOrchestrator.process must be called with the mission's mission_id."""
        (
            p_spec,
            p_mod,
            p_mag,
            fake_mag_orch,
            fake_lead_instance,
            _,
        ) = self._patch_synthesize(orch)

        with p_spec, p_mod, p_mag:
            orch.synthesize_mission(mission, [])

        fake_mag_orch.process.assert_called_once()
        call_args = fake_mag_orch.process.call_args
        assert call_args[0][0] == mission.mission_id

    def test_passes_events_to_magnet_orchestrator(self, orch, mission):
        """MagnetOrchestrator.process receives the events list provided by the caller."""
        events = [
            {"magnet_name": "scope_magnet", "inflection_point": "pre_dispatch", "observed_signal": {}},
            {"magnet_name": "security_magnet", "inflection_point": "post_dispatch", "observed_signal": {}},
        ]
        (
            p_spec,
            p_mod,
            p_mag,
            fake_mag_orch,
            _,
            _,
        ) = self._patch_synthesize(orch)

        with p_spec, p_mod, p_mag:
            orch.synthesize_mission(mission, events)

        call_args = fake_mag_orch.process.call_args
        assert call_args[0][1] is events

    def test_passes_mission_dict_to_agent_lead_run(self, orch, mission):
        """AgentLead.run must receive mission.__dict__."""
        (
            p_spec,
            p_mod,
            p_mag,
            _,
            fake_lead_instance,
            _,
        ) = self._patch_synthesize(orch)

        with p_spec, p_mod, p_mag:
            orch.synthesize_mission(mission, [])

        fake_lead_instance.run.assert_called_once()
        lead_call = fake_lead_instance.run.call_args
        assert lead_call[0][0] == mission.__dict__

    def test_passes_events_to_agent_lead_run(self, orch, mission):
        """AgentLead.run must receive the original events list."""
        events = [{"magnet_name": "test_magnet", "inflection_point": "x", "observed_signal": {}}]
        (
            p_spec,
            p_mod,
            p_mag,
            _,
            fake_lead_instance,
            _,
        ) = self._patch_synthesize(orch)

        with p_spec, p_mod, p_mag:
            orch.synthesize_mission(mission, events)

        lead_call = fake_lead_instance.run.call_args
        assert lead_call[0][1] is events

    def test_passes_report_to_agent_lead_run(self, orch, mission):
        """AgentLead.run must receive the MagnetReport produced by MagnetOrchestrator.process."""
        fake_report = _build_magnet_report_stub()
        (
            p_spec,
            p_mod,
            p_mag,
            fake_mag_orch,
            fake_lead_instance,
            _,
        ) = self._patch_synthesize(orch)
        fake_mag_orch.process.return_value = fake_report

        with p_spec, p_mod, p_mag:
            orch.synthesize_mission(mission, [])

        lead_call = fake_lead_instance.run.call_args
        assert lead_call[0][2] is fake_report

    def test_empty_events_list_accepted(self, orch, mission):
        """synthesize_mission must not raise when events is an empty list."""
        (p_spec, p_mod, p_mag, _, _, fake_output) = self._patch_synthesize(orch)

        with p_spec, p_mod, p_mag:
            result = orch.synthesize_mission(mission, [])

        assert result is fake_output

    def test_agent_lead_loaded_from_same_directory(self, orch, mission):
        """importlib.util.spec_from_file_location must be called with a path ending in agent_lead.py."""
        (p_spec, p_mod, p_mag, _, _, _) = self._patch_synthesize(orch)

        captured_path = []

        def capturing_spec(name, path, **kw):
            captured_path.append(path)
            m = MagicMock()
            m.loader = MagicMock()
            m.loader.exec_module.side_effect = lambda mod: setattr(mod, "AgentLead", MagicMock())
            return m

        with patch("importlib.util.spec_from_file_location", side_effect=capturing_spec), p_mod, p_mag:
            orch.synthesize_mission(mission, [])

        assert len(captured_path) >= 1
        assert captured_path[0].endswith("agent_lead.py")

    def test_agent_lead_module_name_is_agent_lead(self, orch, mission):
        """spec_from_file_location must be called with module name 'agent_lead'."""
        captured_names = []

        def capturing_spec(name, path, **kw):
            captured_names.append(name)
            m = MagicMock()
            m.loader = MagicMock()
            m.loader.exec_module.side_effect = lambda mod: setattr(mod, "AgentLead", MagicMock())
            return m

        fake_mag_orch = MagicMock()
        fake_mag_orch.process.return_value = _build_magnet_report_stub()
        fake_module = types.ModuleType("agent_lead")
        fake_module.AgentLead = MagicMock(return_value=MagicMock(run=MagicMock(return_value=MagicMock())))

        with (
            patch("importlib.util.spec_from_file_location", side_effect=capturing_spec),
            patch("importlib.util.module_from_spec", return_value=fake_module),
            patch("orchestrator_core_under_test.MagnetOrchestrator", return_value=fake_mag_orch),
        ):
            orch.synthesize_mission(mission, [])

        assert "agent_lead" in captured_names

    def test_agent_lead_registered_in_sys_modules(self, orch, mission):
        """After synthesize_mission runs, sys.modules['agent_lead'] must be populated."""
        # Clear any prior registration so we can test the injection behaviour
        sys.modules.pop("agent_lead", None)

        (p_spec, p_mod, p_mag, _, _, _) = self._patch_synthesize(orch)

        with p_spec, p_mod, p_mag:
            orch.synthesize_mission(mission, [])

        assert "agent_lead" in sys.modules

    @pytest.mark.parametrize("decision", ["proceed", "proceed_reversible_only", "replan", "halt", "review"])
    def test_output_decision_reflects_agent_lead_decision(self, orch, mission, decision):
        """The decision field on the returned output must match what AgentLead.run produces."""
        (p_spec, p_mod, p_mag, _, fake_lead_instance, _) = self._patch_synthesize(orch, decision=decision)
        output = self._make_agent_lead_output(decision=decision)
        fake_lead_instance.run.return_value = output

        with p_spec, p_mod, p_mag:
            result = orch.synthesize_mission(mission, [])

        assert result.decision == decision

    def test_synthesize_with_real_magnet_event_dicts(self, orch, mission):
        """Verify synthesize_mission forwards realistic event dicts without raising."""
        events = [
            {
                "mission_id": mission.mission_id,
                "magnet_name": "scope_magnet",
                "inflection_point": "pre_dispatch",
                "observed_signal": {"file_count": 12},
                "risk_delta": 0.0,
                "confidence_delta": 5.0,
                "evidence": ["scope within bounds"],
                "recommended_action": "none",
            },
            {
                "mission_id": mission.mission_id,
                "magnet_name": "security_magnet",
                "inflection_point": "post_work",
                "observed_signal": {"secrets_found": 0},
                "risk_delta": 0.0,
                "confidence_delta": 2.0,
                "evidence": ["no secrets detected"],
                "recommended_action": "none",
            },
        ]

        (p_spec, p_mod, p_mag, fake_mag_orch, _, fake_output) = self._patch_synthesize(orch)

        with p_spec, p_mod, p_mag:
            result = orch.synthesize_mission(mission, events)

        assert result is fake_output
        call_args = fake_mag_orch.process.call_args
        assert call_args[0][1] is events

    def test_high_risk_report_forwards_halt_decision(self, orch, mission):
        """When AgentLead.run returns a halt decision, synthesize_mission propagates it."""
        (p_spec, p_mod, p_mag, _, fake_lead_instance, _) = self._patch_synthesize(orch, decision="halt", score=20.0)
        halt_output = self._make_agent_lead_output(decision="halt", score=20.0)
        fake_lead_instance.run.return_value = halt_output

        with p_spec, p_mod, p_mag:
            result = orch.synthesize_mission(mission, [])

        assert result.decision == "halt"
        assert result.composite_score == 20.0

    def test_synthesize_mission_preserves_mission_metadata(self, orch):
        """Mission metadata must not be mutated by synthesize_mission itself."""
        mp = _make_mission(
            mission_id="CHR-MISSION-META0001",
            metadata={"bead_id": "bd-100", "task_id": "TASK-999"},
        )
        original_meta = dict(mp.metadata)

        (p_spec, p_mod, p_mag, _, _, fake_output) = self._patch_synthesize(orch)

        with p_spec, p_mod, p_mag:
            orch.synthesize_mission(mp, [])

        # synthesize_mission must not alter mission.metadata
        assert mp.metadata == original_meta

    def test_synthesize_mission_calls_magnet_orchestrator_once(self, orch, mission):
        """MagnetOrchestrator.process must be called exactly once per synthesize_mission call."""
        (p_spec, p_mod, p_mag, fake_mag_orch, _, _) = self._patch_synthesize(orch)

        with p_spec, p_mod, p_mag:
            orch.synthesize_mission(mission, [{"magnet_name": "m", "inflection_point": "x", "observed_signal": {}}])

        assert fake_mag_orch.process.call_count == 1

    def test_synthesize_mission_calls_agent_lead_run_once(self, orch, mission):
        """AgentLead.run must be called exactly once per synthesize_mission call."""
        (p_spec, p_mod, p_mag, _, fake_lead_instance, _) = self._patch_synthesize(orch)

        with p_spec, p_mod, p_mag:
            orch.synthesize_mission(mission, [])

        assert fake_lead_instance.run.call_count == 1


# ---------------------------------------------------------------------------
# MissionPacket — data model validation
# ---------------------------------------------------------------------------


class TestMissionPacketDataModel:
    def setup_method(self):
        self.MP = MissionPacket

    def test_all_required_fields_stored(self):
        mp = self.MP(
            mission_id="CHR-MISSION-DM0001",
            objective="validate data model",
            agent_role="worker",
            autonomy_level="L2",
            confidence_required=90.0,
            allowed_tools=["filesystem.read", "filesystem.write"],
            stop_conditions=["confidence_below_threshold"],
            required_outputs=["task_result", "verifier_report"],
        )
        assert mp.mission_id == "CHR-MISSION-DM0001"
        assert mp.objective == "validate data model"
        assert mp.agent_role == "worker"
        assert mp.autonomy_level == "L2"
        assert mp.confidence_required == 90.0
        assert mp.allowed_tools == ["filesystem.read", "filesystem.write"]
        assert mp.stop_conditions == ["confidence_below_threshold"]
        assert mp.required_outputs == ["task_result", "verifier_report"]

    def test_metadata_default_is_empty_dict(self):
        mp = _make_mission()
        assert isinstance(mp.metadata, dict)
        assert mp.metadata == {}

    def test_metadata_accepts_arbitrary_keys(self):
        mp = _make_mission(metadata={"bead_id": "bd-99", "custom_key": [1, 2, 3]})
        assert mp.metadata["bead_id"] == "bd-99"
        assert mp.metadata["custom_key"] == [1, 2, 3]

    def test_metadata_instances_are_independent(self):
        """Each MissionPacket must have its own metadata dict (no shared mutable default)."""
        mp1 = _make_mission()
        mp2 = _make_mission()
        mp1.metadata["x"] = 1
        assert "x" not in mp2.metadata

    def test_allowed_tools_is_list(self):
        mp = _make_mission()
        assert isinstance(mp.allowed_tools, list)

    def test_stop_conditions_is_list(self):
        mp = _make_mission()
        assert isinstance(mp.stop_conditions, list)

    def test_required_outputs_is_list(self):
        mp = _make_mission()
        assert isinstance(mp.required_outputs, list)

    def test_confidence_required_stored_as_float(self):
        mp = _make_mission(confidence_required=85)
        # Stored value type is whatever caller passes — at minimum it round-trips
        assert mp.confidence_required == 85


# ---------------------------------------------------------------------------
# create_mission
# ---------------------------------------------------------------------------


class TestCreateMission:
    def setup_method(self):
        self.orch = Orchestrator()

    def test_returns_mission_packet_type(self):

        result = self.orch.create_mission("write integration tests")
        assert isinstance(result, MissionPacket)

    def test_objective_matches_intent(self):
        result = self.orch.create_mission("implement payment service")
        assert result.objective == "implement payment service"

    def test_mission_id_prefix(self):
        result = self.orch.create_mission("x")
        assert result.mission_id.startswith("CHR-MISSION-")

    def test_mission_id_suffix_is_8_chars(self):
        result = self.orch.create_mission("x")
        suffix = result.mission_id[len("CHR-MISSION-") :]
        assert len(suffix) == 8

    def test_mission_id_suffix_is_uppercase(self):
        result = self.orch.create_mission("x")
        suffix = result.mission_id[len("CHR-MISSION-") :]
        assert suffix == suffix.upper()

    def test_mission_id_unique_per_call(self):
        ids = {self.orch.create_mission("same intent").mission_id for _ in range(20)}
        assert len(ids) == 20

    def test_agent_role_is_agent_lead(self):
        assert self.orch.create_mission("x").agent_role == "agent_lead"

    def test_autonomy_level_is_l1(self):
        assert self.orch.create_mission("x").autonomy_level == "L1"

    def test_confidence_required_is_75(self):
        assert self.orch.create_mission("x").confidence_required == 75

    def test_allowed_tools_contains_filesystem_read(self):
        assert "filesystem.read" in self.orch.create_mission("x").allowed_tools

    def test_stop_conditions_contains_confidence_below_threshold(self):
        result = self.orch.create_mission("x")
        assert "confidence_below_threshold" in result.stop_conditions

    def test_stop_conditions_contains_scope_unclear(self):
        assert "scope_unclear" in self.orch.create_mission("x").stop_conditions

    def test_stop_conditions_contains_security_risk_detected(self):
        assert "security_risk_detected" in self.orch.create_mission("x").stop_conditions

    def test_required_outputs_contains_agent_lead_report(self):
        assert "agent_lead_report" in self.orch.create_mission("x").required_outputs

    def test_required_outputs_contains_next_bead(self):
        assert "next_bead" in self.orch.create_mission("x").required_outputs

    def test_empty_intent_still_creates_mission(self):
        result = self.orch.create_mission("")
        assert result.objective == ""

    def test_metadata_defaults_empty(self):
        assert self.orch.create_mission("x").metadata == {}


# ---------------------------------------------------------------------------
# create_mission_from_task
# ---------------------------------------------------------------------------


class TestCreateMissionFromTask:
    def setup_method(self):
        self.orch = Orchestrator()

    def _task(self, **kw):
        base = {
            "title": "Default title",
            "confidence_required": 75.0,
            "role": "worker",
            "tool_budget": 5,
        }
        base.update(kw)
        return base

    def test_objective_from_title_key(self):
        result = self.orch.create_mission_from_task(self._task(title="Fix DB migration"))
        assert result.objective == "Fix DB migration"

    def test_objective_fallback_to_objective_key(self):
        result = self.orch.create_mission_from_task({"objective": "fallback obj"})
        assert result.objective == "fallback obj"

    def test_title_takes_precedence_over_objective(self):
        result = self.orch.create_mission_from_task({"title": "title wins", "objective": "obj loses"})
        assert result.objective == "title wins"

    def test_empty_task_dict_uses_empty_string_objective(self):
        result = self.orch.create_mission_from_task({})
        assert result.objective == ""

    def test_confidence_required_from_confidence_required_key(self):
        result = self.orch.create_mission_from_task(self._task(confidence_required=88.5))
        assert result.confidence_required == 88.5

    def test_confidence_required_from_confidence_score_fallback(self):
        result = self.orch.create_mission_from_task({"title": "t", "confidence_score": 62.0})
        assert result.confidence_required == 62.0

    def test_confidence_required_default_is_75(self):
        result = self.orch.create_mission_from_task({"title": "t"})
        assert result.confidence_required == 75.0

    def test_confidence_required_is_float(self):
        result = self.orch.create_mission_from_task(self._task(confidence_required=80))
        assert isinstance(result.confidence_required, float)

    def test_role_from_task(self):
        result = self.orch.create_mission_from_task(self._task(role="reviewer"))
        assert result.agent_role == "reviewer"

    def test_role_defaults_to_worker(self):
        result = self.orch.create_mission_from_task({"title": "t"})
        assert result.agent_role == "worker"

    @pytest.mark.parametrize(
        "budget,expected_level",
        [
            (0, "L1"),
            (1, "L1"),
            (20, "L1"),
            (21, "L2"),
            (100, "L2"),
        ],
    )
    def test_autonomy_level_based_on_tool_budget(self, budget, expected_level):
        result = self.orch.create_mission_from_task(self._task(tool_budget=budget))
        assert result.autonomy_level == expected_level

    def test_allowed_files_present_adds_write_tool(self):
        result = self.orch.create_mission_from_task(self._task(allowed_files=["src/foo.py"]))
        assert "filesystem.write" in result.allowed_tools

    def test_allowed_files_empty_no_write_tool(self):
        result = self.orch.create_mission_from_task(self._task(allowed_files=[]))
        assert "filesystem.write" not in result.allowed_tools

    def test_no_allowed_files_key_no_write_tool(self):
        result = self.orch.create_mission_from_task(self._task())
        assert "filesystem.write" not in result.allowed_tools

    def test_filesystem_read_always_present(self):
        result = self.orch.create_mission_from_task({})
        assert "filesystem.read" in result.allowed_tools

    def test_custom_stop_conditions(self):
        result = self.orch.create_mission_from_task(self._task(stop_conditions=["halt_on_secret"]))
        assert result.stop_conditions == ["halt_on_secret"]

    def test_default_stop_conditions_populated(self):
        result = self.orch.create_mission_from_task({"title": "t"})
        assert len(result.stop_conditions) >= 3

    def test_required_outputs_task_result(self):
        assert "task_result" in self.orch.create_mission_from_task(self._task()).required_outputs

    def test_required_outputs_verifier_report(self):
        assert "verifier_report" in self.orch.create_mission_from_task(self._task()).required_outputs

    def test_metadata_task_id(self):
        result = self.orch.create_mission_from_task(self._task(task_id="TASK-007"))
        assert result.metadata["task_id"] == "TASK-007"

    def test_metadata_task_id_empty_string_default(self):
        result = self.orch.create_mission_from_task({"title": "t"})
        assert result.metadata["task_id"] == ""

    def test_metadata_assigned_model(self):
        result = self.orch.create_mission_from_task(self._task(assigned_model="claude-sonnet-4-5"))
        assert result.metadata["assigned_model"] == "claude-sonnet-4-5"

    def test_metadata_allowed_files_stored(self):
        files = ["src/a.py", "src/b.py"]
        result = self.orch.create_mission_from_task(self._task(allowed_files=files))
        assert result.metadata["allowed_files"] == files

    def test_metadata_tool_budget_stored(self):
        result = self.orch.create_mission_from_task(self._task(tool_budget=15))
        assert result.metadata["tool_budget"] == 15

    def test_metadata_bead_id_stored(self):
        result = self.orch.create_mission_from_task(self._task(bead_id="bd-55"))
        assert result.metadata["bead_id"] == "bd-55"

    def test_mission_id_unique_per_call(self):
        ids = {self.orch.create_mission_from_task(self._task()).mission_id for _ in range(10)}
        assert len(ids) == 10


# ---------------------------------------------------------------------------
# attach_magnets
# ---------------------------------------------------------------------------


class TestAttachMagnets:
    def setup_method(self):
        # Patch MagnetOrchestrator at the module level so attach_magnets doesn't
        # try to instantiate the real registry (which transitively imports yaml).
        self._mag_orch_cls = MagicMock()
        self._mag_orch_inst = MagicMock()
        self._mag_orch_inst.registered_magnets.return_value = ["scope_magnet", "security_magnet"]
        self._mag_orch_cls.return_value = self._mag_orch_inst
        self._patcher = patch("orchestrator_core_under_test.MagnetOrchestrator", self._mag_orch_cls)
        self._patcher.start()
        self.orch = Orchestrator()

    def teardown_method(self):
        self._patcher.stop()

    def test_returns_list(self):
        result = self.orch.attach_magnets(_make_mission())
        assert isinstance(result, list)

    def test_returns_magnet_names_from_registry(self):
        result = self.orch.attach_magnets(_make_mission())
        assert "scope_magnet" in result
        assert "security_magnet" in result

    def test_ignores_mission_content(self):
        """attach_magnets must return the same registry regardless of mission content."""
        r1 = self.orch.attach_magnets(_make_mission(objective="task A"))
        r2 = self.orch.attach_magnets(_make_mission(objective="task B"))
        assert r1 == r2

    def test_delegates_to_magnet_orchestrator_registered_magnets(self):
        """attach_magnets must delegate to MagnetOrchestrator().registered_magnets()."""
        custom_magnets = ["alpha_magnet", "beta_magnet"]
        mag_orch_cls = MagicMock()
        mag_orch_instance = MagicMock()
        mag_orch_instance.registered_magnets.return_value = custom_magnets
        mag_orch_cls.return_value = mag_orch_instance

        with patch("orchestrator_core_under_test.MagnetOrchestrator", mag_orch_cls):
            result = self.orch.attach_magnets(_make_mission())

        assert result == custom_magnets


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


class TestDispatch:
    def setup_method(self):
        # dispatch() → attach_magnets() → MagnetOrchestrator(); stub it out
        self._mag_orch_cls = MagicMock()
        self._mag_orch_inst = MagicMock()
        self._mag_orch_inst.registered_magnets.return_value = ["scope_magnet", "security_magnet"]
        self._mag_orch_cls.return_value = self._mag_orch_inst
        self._patcher = patch("orchestrator_core_under_test.MagnetOrchestrator", self._mag_orch_cls)
        self._patcher.start()
        self.orch = Orchestrator()

    def teardown_method(self):
        self._patcher.stop()

    def test_returns_dict(self):
        assert isinstance(self.orch.dispatch(_make_mission()), dict)

    def test_mission_id_in_result(self):
        mp = _make_mission(mission_id="CHR-MISSION-DISP0001")
        result = self.orch.dispatch(mp)
        assert result["mission_id"] == "CHR-MISSION-DISP0001"

    def test_status_is_ready_for_runtime(self):
        assert self.orch.dispatch(_make_mission())["status"] == "ready_for_runtime"

    def test_magnets_key_present(self):
        assert "magnets" in self.orch.dispatch(_make_mission())

    def test_magnets_is_list(self):
        assert isinstance(self.orch.dispatch(_make_mission())["magnets"], list)

    def test_result_keys_exactly_three(self):
        result = self.orch.dispatch(_make_mission())
        assert set(result.keys()) == {"mission_id", "status", "magnets"}

    def test_dispatch_twice_same_mission_consistent(self):
        mp = _make_mission()
        r1 = self.orch.dispatch(mp)
        r2 = self.orch.dispatch(mp)
        assert r1["mission_id"] == r2["mission_id"]
        assert r1["status"] == r2["status"]

    def test_dispatch_different_missions_different_ids(self):
        mp1 = _make_mission(mission_id="CHR-MISSION-DIFF0001")
        mp2 = _make_mission(mission_id="CHR-MISSION-DIFF0002")
        assert self.orch.dispatch(mp1)["mission_id"] != self.orch.dispatch(mp2)["mission_id"]


# ---------------------------------------------------------------------------
# guard_and_inject (async)
# ---------------------------------------------------------------------------


class TestGuardAndInject:
    @pytest.fixture(autouse=True)
    def _stub_guard(self):
        """Ensure scope.guard stub is properly configured for each test."""
        _ensure_stubs()

    def _mp(self, **overrides):
        return _make_mission(
            mission_id="CHR-MISSION-GUARD001",
            objective="review codebase",
            **overrides,
        )

    @pytest.mark.asyncio
    async def test_returns_dict(self, orch):
        result = await orch.guard_and_inject(self._mp())
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_status_is_guarded_and_ready(self, orch):
        result = await orch.guard_and_inject(self._mp())
        assert result["status"] == "guarded_and_ready"

    @pytest.mark.asyncio
    async def test_mission_id_preserved(self, orch):
        mp = self._mp()
        result = await orch.guard_and_inject(mp)
        assert result["mission_id"] == mp.mission_id

    @pytest.mark.asyncio
    async def test_result_contains_scope_baseline(self, orch):
        result = await orch.guard_and_inject(self._mp(), file_scope="02_RUNTIME/")
        assert "scope_baseline" in result

    @pytest.mark.asyncio
    async def test_scope_baseline_has_expected_scope(self, orch):
        result = await orch.guard_and_inject(self._mp(), file_scope="02_RUNTIME/")
        sb = result["scope_baseline"]
        assert "expected_scope" in sb

    @pytest.mark.asyncio
    async def test_scope_baseline_has_baseline_count(self, orch):
        result = await orch.guard_and_inject(self._mp(), file_scope="02_RUNTIME/")
        sb = result["scope_baseline"]
        assert "baseline_count" in sb

    @pytest.mark.asyncio
    async def test_injected_rules_is_list(self, orch):
        result = await orch.guard_and_inject(self._mp())
        assert isinstance(result["injected_rules"], list)

    @pytest.mark.asyncio
    async def test_injected_rules_names_extracted(self, orch):
        result = await orch.guard_and_inject(self._mp())
        # Stub (local) returns "file_scope_rule"; real DispatchGuard (CI) returns "FILE_SCOPE_ENFORCEMENT"
        assert any(r in result["injected_rules"] for r in ("file_scope_rule", "FILE_SCOPE_ENFORCEMENT"))

    @pytest.mark.asyncio
    async def test_scope_header_present_true_when_scope_non_empty(self, orch):
        result = await orch.guard_and_inject(self._mp(), file_scope="02_RUNTIME/")
        assert result["scope_header_present"] is True

    @pytest.mark.asyncio
    async def test_scope_header_present_false_when_no_scope_header(self, orch):
        # Override the stub to return empty scope_header
        dg_cls = MagicMock()
        dg_instance = AsyncMock()
        guarded = MagicMock()
        guarded.mission = {"metadata": {}}
        guarded.scope_baseline = None
        guarded.injected_context = {"governance_rules": []}
        guarded.scope_header = ""  # empty → False
        dg_instance.guard.return_value = guarded
        dg_cls.return_value = dg_instance

        with patch("orchestrator_core_under_test.DispatchGuard", dg_cls):
            orch_local = Orchestrator()
            result = await orch_local.guard_and_inject(self._mp(), file_scope="")

        assert result["scope_header_present"] is False

    @pytest.mark.asyncio
    async def test_scope_baseline_none_when_guard_returns_none_baseline(self, orch):
        """When scope_baseline is None, scope_baseline dict must have empty strings/zero counts."""
        dg_cls = MagicMock()
        dg_instance = AsyncMock()
        guarded = MagicMock()
        guarded.mission = {"metadata": {}}
        guarded.scope_baseline = None
        guarded.injected_context = {"governance_rules": []}
        guarded.scope_header = ""
        dg_instance.guard.return_value = guarded
        dg_cls.return_value = dg_instance

        with patch("orchestrator_core_under_test.DispatchGuard", dg_cls):
            orch_local = Orchestrator()
            result = await orch_local.guard_and_inject(self._mp())

        assert result["scope_baseline"]["expected_scope"] == ""
        assert result["scope_baseline"]["baseline_count"] == 0

    @pytest.mark.asyncio
    async def test_metadata_updated_with_injected_context(self, orch):
        """Mission metadata must be updated with guarded.mission['metadata']."""
        extra_meta = {"injected_key": "injected_value"}
        dg_cls = MagicMock()
        dg_instance = AsyncMock()
        guarded = MagicMock()
        guarded.mission = {"metadata": extra_meta}
        guarded.scope_baseline = MagicMock(expected_scope="02_RUNTIME/", baseline_count=5)
        guarded.injected_context = {"governance_rules": []}
        guarded.scope_header = "header"
        dg_instance.guard.return_value = guarded
        dg_cls.return_value = dg_instance

        with patch("orchestrator_core_under_test.DispatchGuard", dg_cls):
            orch_local = Orchestrator()
            mp = self._mp()
            await orch_local.guard_and_inject(mp)

        assert mp.metadata.get("injected_key") == "injected_value"

    @pytest.mark.asyncio
    async def test_guard_called_with_file_scope(self, orch):
        """DispatchGuard.guard must receive file_scope keyword argument."""
        dg_cls = MagicMock()
        dg_instance = AsyncMock()
        guarded = MagicMock()
        guarded.mission = {"metadata": {}}
        guarded.scope_baseline = MagicMock(expected_scope="tests/", baseline_count=2)
        guarded.injected_context = {"governance_rules": []}
        guarded.scope_header = "header"
        dg_instance.guard.return_value = guarded
        dg_cls.return_value = dg_instance

        with patch("orchestrator_core_under_test.DispatchGuard", dg_cls):
            orch_local = Orchestrator()
            await orch_local.guard_and_inject(self._mp(), file_scope="tests/")

        _, call_kwargs = dg_instance.guard.call_args
        assert call_kwargs.get("file_scope") == "tests/"

    @pytest.mark.asyncio
    async def test_guard_called_with_agent_id(self, orch):
        """DispatchGuard.guard must receive agent_id keyword argument."""
        dg_cls = MagicMock()
        dg_instance = AsyncMock()
        guarded = MagicMock()
        guarded.mission = {"metadata": {}}
        guarded.scope_baseline = None
        guarded.injected_context = {"governance_rules": []}
        guarded.scope_header = ""
        dg_instance.guard.return_value = guarded
        dg_cls.return_value = dg_instance

        with patch("orchestrator_core_under_test.DispatchGuard", dg_cls):
            orch_local = Orchestrator()
            await orch_local.guard_and_inject(self._mp(), agent_id="my_custom_agent")

        _, call_kwargs = dg_instance.guard.call_args
        assert call_kwargs.get("agent_id") == "my_custom_agent"


# ---------------------------------------------------------------------------
# verify_scope_after_work (async)
# ---------------------------------------------------------------------------


class TestVerifyScopeAfterWork:
    def _mp(self):
        return _make_mission(mission_id="CHR-MISSION-VERIFY01")

    @pytest.mark.asyncio
    async def test_no_scope_declared_returns_passed_true(self, orch):
        result = await orch.verify_scope_after_work(self._mp(), baseline={})
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_no_scope_declared_reason_no_scope_declared(self, orch):
        result = await orch.verify_scope_after_work(self._mp(), baseline={})
        assert result["reason"] == "no_scope_declared"

    @pytest.mark.asyncio
    async def test_empty_expected_scope_returns_passed(self, orch):
        result = await orch.verify_scope_after_work(self._mp(), baseline={"expected_scope": ""})
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_with_scope_returns_dict_with_violations(self, orch):
        mock_result = MagicMock(passed=True, violations=[], new_files=[], modified_outside=[])
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

        assert "violations" in result

    @pytest.mark.asyncio
    async def test_with_scope_returns_new_files_outside_scope(self, orch):
        mock_result = MagicMock(passed=True, violations=[], new_files=[], modified_outside=[])
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

        assert "new_files_outside_scope" in result

    @pytest.mark.asyncio
    async def test_with_scope_returns_modified_outside_scope(self, orch):
        mock_result = MagicMock(passed=True, violations=[], new_files=[], modified_outside=[])
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

        assert "modified_outside_scope" in result

    @pytest.mark.asyncio
    async def test_scope_violation_propagates_passed_false(self, orch):
        mock_result = MagicMock(
            passed=False,
            violations=["modified outside scope: src/other.py"],
            new_files=[],
            modified_outside=["src/other.py"],
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

        assert result["passed"] is False
        assert len(result["violations"]) > 0

    @pytest.mark.asyncio
    async def test_scope_new_files_outside_scope(self, orch):
        mock_result = MagicMock(
            passed=False,
            violations=["created outside scope: leaked.py"],
            new_files=["leaked.py"],
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
                baseline={"expected_scope": "02_RUNTIME/", "baseline_count": 3},
            )

        assert result["new_files_outside_scope"] == ["leaked.py"]

    @pytest.mark.asyncio
    async def test_scope_enforcer_called_with_correct_mission_id(self, orch):
        """ScopeEnforcer.enforce_and_log must be called with a ScopeBaseline carrying the mission_id."""
        captured_baseline = []

        class _FakeScopeBaseline:
            def __init__(self, **kw):
                for k, v in kw.items():
                    setattr(self, k, v)
                captured_baseline.append(self)

        mock_result = MagicMock(passed=True, violations=[], new_files=[], modified_outside=[])
        mock_enforcer = AsyncMock()
        mock_enforcer.enforce_and_log.return_value = mock_result

        with (
            patch("scope.enforcer.ScopeEnforcer", return_value=mock_enforcer),
            patch("scope.enforcer.ScopeBaseline", _FakeScopeBaseline),
        ):
            mp = self._mp()
            await orch.verify_scope_after_work(
                mp,
                baseline={"expected_scope": "02_RUNTIME/", "baseline_count": 7},
            )

        assert len(captured_baseline) == 1
        assert captured_baseline[0].mission_id == mp.mission_id

    @pytest.mark.asyncio
    async def test_baseline_count_defaults_to_zero_when_missing(self, orch):
        """If baseline_count is absent, ScopeBaseline must receive baseline_count=0."""
        captured = []

        class _FakeScopeBaseline:
            def __init__(self, **kw):
                captured.append(kw)

        mock_result = MagicMock(passed=True, violations=[], new_files=[], modified_outside=[])
        mock_enforcer = AsyncMock()
        mock_enforcer.enforce_and_log.return_value = mock_result

        with (
            patch("scope.enforcer.ScopeEnforcer", return_value=mock_enforcer),
            patch("scope.enforcer.ScopeBaseline", _FakeScopeBaseline),
        ):
            await orch.verify_scope_after_work(
                self._mp(),
                baseline={"expected_scope": "02_RUNTIME/"},
            )

        assert captured[0]["baseline_count"] == 0


# ---------------------------------------------------------------------------
# route_to_provider (async)
# ---------------------------------------------------------------------------


class TestRouteToProvider:
    def _mp(self):
        return _make_mission(
            mission_id="CHR-MISSION-ROUTE001",
            objective="plan sprint",
        )

    def _fake_route_resp(self, **overrides):
        defaults = dict(
            selected_provider="anthropic",
            selected_model="claude-sonnet-4-5",
            route_reason="best fit",
            fallback_used=False,
            cost_estimate_usd=0.01,
            latency_ms=200,
            logs=MagicMock(warnings=[], errors=[]),
        )
        defaults.update(overrides)
        return MagicMock(**defaults)

    @pytest.mark.asyncio
    async def test_returns_dict(self):
        orch = Orchestrator()
        mock_router = AsyncMock()
        mock_router.route.return_value = self._fake_route_resp()

        with patch("orchestrator_core_under_test.ChromaticRouter", return_value=mock_router):
            result = await orch.route_to_provider(self._mp())

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_provider_key_in_result(self):
        orch = Orchestrator()
        mock_router = AsyncMock()
        mock_router.route.return_value = self._fake_route_resp(selected_provider="openai")

        with patch("orchestrator_core_under_test.ChromaticRouter", return_value=mock_router):
            result = await orch.route_to_provider(self._mp())

        assert result["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_model_key_in_result(self):
        orch = Orchestrator()
        mock_router = AsyncMock()
        mock_router.route.return_value = self._fake_route_resp(selected_model="gpt-4o")

        with patch("orchestrator_core_under_test.ChromaticRouter", return_value=mock_router):
            result = await orch.route_to_provider(self._mp())

        assert result["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_reason_key_in_result(self):
        orch = Orchestrator()
        mock_router = AsyncMock()
        mock_router.route.return_value = self._fake_route_resp(route_reason="privacy constraint")

        with patch("orchestrator_core_under_test.ChromaticRouter", return_value=mock_router):
            result = await orch.route_to_provider(self._mp())

        assert result["reason"] == "privacy constraint"

    @pytest.mark.asyncio
    async def test_fallback_used_key_in_result(self):
        orch = Orchestrator()
        mock_router = AsyncMock()
        mock_router.route.return_value = self._fake_route_resp(fallback_used=True)

        with patch("orchestrator_core_under_test.ChromaticRouter", return_value=mock_router):
            result = await orch.route_to_provider(self._mp())

        assert result["fallback_used"] is True

    @pytest.mark.asyncio
    async def test_latency_ms_is_int(self):
        orch = Orchestrator()
        mock_router = AsyncMock()
        mock_router.route.return_value = self._fake_route_resp(latency_ms=350.7)

        with patch("orchestrator_core_under_test.ChromaticRouter", return_value=mock_router):
            result = await orch.route_to_provider(self._mp())

        assert isinstance(result["latency_ms"], int)
        assert result["latency_ms"] == 350

    @pytest.mark.asyncio
    async def test_none_latency_ms_becomes_zero(self):
        orch = Orchestrator()
        mock_router = AsyncMock()
        mock_router.route.return_value = self._fake_route_resp(latency_ms=None)

        with patch("orchestrator_core_under_test.ChromaticRouter", return_value=mock_router):
            result = await orch.route_to_provider(self._mp())

        assert result["latency_ms"] == 0

    @pytest.mark.asyncio
    async def test_warnings_passed_through(self):
        orch = Orchestrator()
        mock_router = AsyncMock()
        resp = self._fake_route_resp()
        resp.logs = MagicMock(warnings=["rate_limit_warning"], errors=[])
        mock_router.route.return_value = resp

        with patch("orchestrator_core_under_test.ChromaticRouter", return_value=mock_router):
            result = await orch.route_to_provider(self._mp())

        assert result["warnings"] == ["rate_limit_warning"]

    @pytest.mark.asyncio
    async def test_errors_passed_through(self):
        orch = Orchestrator()
        mock_router = AsyncMock()
        resp = self._fake_route_resp()
        resp.logs = MagicMock(warnings=[], errors=["provider_unavailable"])
        mock_router.route.return_value = resp

        with patch("orchestrator_core_under_test.ChromaticRouter", return_value=mock_router):
            result = await orch.route_to_provider(self._mp())

        assert result["errors"] == ["provider_unavailable"]

    @pytest.mark.parametrize("task_type", ["planning", "coding", "review"])
    @pytest.mark.asyncio
    async def test_task_type_forwarded_to_route_request(self, task_type):
        orch = Orchestrator()
        mock_router = AsyncMock()
        mock_router.route.return_value = self._fake_route_resp()

        with patch("orchestrator_core_under_test.ChromaticRouter", return_value=mock_router):
            await orch.route_to_provider(self._mp(), task_type=task_type)

        call_args = mock_router.route.call_args
        req = call_args[0][0]
        assert req.task_type.value == task_type

    @pytest.mark.asyncio
    async def test_mission_objective_forwarded_to_route_request(self):
        orch = Orchestrator()
        mp = _make_mission(objective="specific objective text")
        mock_router = AsyncMock()
        mock_router.route.return_value = self._fake_route_resp()

        with patch("orchestrator_core_under_test.ChromaticRouter", return_value=mock_router):
            await orch.route_to_provider(mp)

        call_args = mock_router.route.call_args
        req = call_args[0][0]
        assert req.objective == "specific objective text"

    @pytest.mark.asyncio
    async def test_cost_estimate_usd_in_result(self):
        orch = Orchestrator()
        mock_router = AsyncMock()
        mock_router.route.return_value = self._fake_route_resp(cost_estimate_usd=0.05)

        with patch("orchestrator_core_under_test.ChromaticRouter", return_value=mock_router):
            result = await orch.route_to_provider(self._mp())

        assert result["cost_estimate_usd"] == 0.05


# ---------------------------------------------------------------------------
# complete_mission
# ---------------------------------------------------------------------------


class TestCompleteMission:
    def _mp(self, **overrides):
        defaults = {"mission_id": "CHR-MISSION-DONE0001", "confidence_required": 80.0}
        defaults.update(overrides)
        return _make_mission(**defaults)

    def test_does_not_raise_with_full_args(self, orch):
        orch.complete_mission(
            self._mp(),
            model="claude-sonnet-4-5",
            role="worker",
            files_touched=["src/module.py"],
            result="task_result",
            validation="tests_passed",
            next_task="CHR-NEXT-001",
            tools_used=7,
        )

    def test_does_not_raise_with_minimal_args(self, orch):
        orch.complete_mission(
            self._mp(),
            model="claude-haiku",
            role="reviewer",
            files_touched=[],
            result="review_complete",
        )

    def test_logger_log_agent_run_called(self, orch):
        """ObservabilityLogger._log_agent_run must be called once per complete_mission."""
        obs_instance = MagicMock()
        obs_cls = MagicMock(return_value=obs_instance)

        with patch("router.observability.ObservabilityLogger", obs_cls):
            orch.complete_mission(
                self._mp(),
                model="claude-sonnet-4-5",
                role="worker",
                files_touched=[],
                result="task_result",
            )

        obs_instance._log_agent_run.assert_called_once()

    def test_confidence_gate_band_from_score_called_with_confidence(self, orch):
        """ConfidenceGate.band_from_score must be called with mission.confidence_required."""
        cg_mock = MagicMock()
        cg_mock.band_from_score.return_value = MagicMock(value="high")

        with patch("router.confidence.ConfidenceGate", cg_mock):
            orch.complete_mission(
                self._mp(),  # _mp() already sets confidence_required=80.0
                model="claude-haiku",
                role="worker",
                files_touched=[],
                result="task_result",
            )

        cg_mock.band_from_score.assert_called_once_with(80.0)

    def test_files_touched_forwarded_to_logger(self, orch):
        """The files_touched list must appear in the extra dict passed to _log_agent_run."""
        obs_instance = MagicMock()
        obs_cls = MagicMock(return_value=obs_instance)

        with patch("router.observability.ObservabilityLogger", obs_cls):
            orch.complete_mission(
                self._mp(),
                model="claude-sonnet-4-5",
                role="worker",
                files_touched=["src/a.py", "src/b.py"],
                result="task_result",
            )

        call_kwargs = obs_instance._log_agent_run.call_args[1]
        extra = call_kwargs.get("extra", {})
        assert extra.get("files_touched") == ["src/a.py", "src/b.py"]

    def test_role_forwarded_to_logger(self, orch):
        obs_instance = MagicMock()
        obs_cls = MagicMock(return_value=obs_instance)

        with patch("router.observability.ObservabilityLogger", obs_cls):
            orch.complete_mission(
                self._mp(),
                model="claude-sonnet-4-5",
                role="agent_lead",
                files_touched=[],
                result="task_result",
            )

        extra = obs_instance._log_agent_run.call_args[1].get("extra", {})
        assert extra.get("role") == "agent_lead"

    def test_tools_used_forwarded_to_logger(self, orch):
        obs_instance = MagicMock()
        obs_cls = MagicMock(return_value=obs_instance)

        with patch("router.observability.ObservabilityLogger", obs_cls):
            orch.complete_mission(
                self._mp(),
                model="claude-sonnet-4-5",
                role="worker",
                files_touched=[],
                result="task_result",
                tools_used=12,
            )

        extra = obs_instance._log_agent_run.call_args[1].get("extra", {})
        assert extra.get("tools_used") == 12

    def test_validation_forwarded_to_logger(self, orch):
        obs_instance = MagicMock()
        obs_cls = MagicMock(return_value=obs_instance)

        with patch("router.observability.ObservabilityLogger", obs_cls):
            orch.complete_mission(
                self._mp(),
                model="claude-sonnet-4-5",
                role="worker",
                files_touched=[],
                result="task_result",
                validation="all_tests_green",
            )

        extra = obs_instance._log_agent_run.call_args[1].get("extra", {})
        assert extra.get("validation") == "all_tests_green"

    def test_next_task_forwarded_to_logger(self, orch):
        obs_instance = MagicMock()
        obs_cls = MagicMock(return_value=obs_instance)

        with patch("router.observability.ObservabilityLogger", obs_cls):
            orch.complete_mission(
                self._mp(),
                model="claude-sonnet-4-5",
                role="worker",
                files_touched=[],
                result="task_result",
                next_task="CHR-NEXT-999",
            )

        extra = obs_instance._log_agent_run.call_args[1].get("extra", {})
        assert extra.get("next_task") == "CHR-NEXT-999"

    def test_fake_req_task_id_matches_mission_id(self, orch):
        """The fake request object must carry mission.mission_id as task_id."""
        obs_instance = MagicMock()
        obs_cls = MagicMock(return_value=obs_instance)
        mp = self._mp(mission_id="CHR-MISSION-DONE0001")

        with patch("router.observability.ObservabilityLogger", obs_cls):
            orch.complete_mission(
                mp,
                model="claude-haiku",
                role="worker",
                files_touched=[],
                result="task_result",
            )

        positional_args = obs_instance._log_agent_run.call_args[0]
        fake_req = positional_args[0]
        assert fake_req.task_id == "CHR-MISSION-DONE0001"

    def test_fake_resp_model_matches_model_arg(self, orch):
        """The fake response object must carry the model string passed to complete_mission."""
        obs_instance = MagicMock()
        obs_cls = MagicMock(return_value=obs_instance)

        with patch("router.observability.ObservabilityLogger", obs_cls):
            orch.complete_mission(
                self._mp(),
                model="my-custom-model",
                role="worker",
                files_touched=[],
                result="task_result",
            )

        positional_args = obs_instance._log_agent_run.call_args[0]
        fake_resp = positional_args[1]
        assert fake_resp.selected_model == "my-custom-model"


# ---------------------------------------------------------------------------
# State machine / lifecycle integration
# ---------------------------------------------------------------------------


class TestLifecycleIntegration:
    """Cross-method lifecycle tests covering create → guard → dispatch → complete."""

    def setup_method(self):
        self._mag_orch_cls = MagicMock()
        self._mag_orch_inst = MagicMock()
        self._mag_orch_inst.registered_magnets.return_value = ["scope_magnet", "security_magnet"]
        self._mag_orch_cls.return_value = self._mag_orch_inst
        self._patcher = patch("orchestrator_core_under_test.MagnetOrchestrator", self._mag_orch_cls)
        self._patcher.start()
        self.orch = Orchestrator()

    def teardown_method(self):
        self._patcher.stop()

    def test_create_then_dispatch_preserves_mission_id(self):
        mp = self.orch.create_mission("build feature Y")
        assert self.orch.dispatch(mp)["mission_id"] == mp.mission_id

    def test_create_from_task_then_dispatch_status(self):
        mp = self.orch.create_mission_from_task({"title": "fix bug", "tool_budget": 5})
        assert self.orch.dispatch(mp)["status"] == "ready_for_runtime"

    def test_high_tool_budget_l2_dispatches_correctly(self):
        mp = self.orch.create_mission_from_task({"title": "big task", "tool_budget": 50})
        assert mp.autonomy_level == "L2"
        result = self.orch.dispatch(mp)
        assert result["status"] == "ready_for_runtime"

    def test_dispatch_twice_same_mission_consistent(self):
        mp = self.orch.create_mission("run twice")
        r1 = self.orch.dispatch(mp)
        r2 = self.orch.dispatch(mp)
        assert r1["mission_id"] == r2["mission_id"]
        assert r1["status"] == r2["status"]

    def test_custom_stop_conditions_preserved_after_dispatch(self):
        mp = self.orch.create_mission_from_task({"title": "t", "stop_conditions": ["custom_halt"]})
        self.orch.dispatch(mp)  # dispatch must not mutate mission
        assert "custom_halt" in mp.stop_conditions

    @pytest.mark.asyncio
    async def test_full_lifecycle_create_guard_dispatch(self):
        # Use self.orch which already has MagnetOrchestrator patched in setup_method
        mp = self.orch.create_mission("full lifecycle test")
        guard_result = await self.orch.guard_and_inject(mp, file_scope="")
        dispatch_result = self.orch.dispatch(mp)
        assert guard_result["mission_id"] == dispatch_result["mission_id"]
        assert dispatch_result["status"] == "ready_for_runtime"

    @pytest.mark.asyncio
    async def test_guard_then_verify_no_scope_passthrough(self):
        """guard_and_inject followed by verify_scope_after_work with empty scope must pass."""
        mp = self.orch.create_mission("verify after guard")
        await self.orch.guard_and_inject(mp, file_scope="")
        result = await self.orch.verify_scope_after_work(mp, baseline={})
        assert result["passed"] is True

    def test_multiple_missions_have_independent_metadata(self):
        mp1 = self.orch.create_mission_from_task({"title": "task1", "bead_id": "b1"})
        mp2 = self.orch.create_mission_from_task({"title": "task2", "bead_id": "b2"})
        mp1.metadata["extra"] = "only_on_1"
        assert "extra" not in mp2.metadata

    @pytest.mark.asyncio
    async def test_route_then_complete_does_not_raise(self):
        """route_to_provider result can feed complete_mission without errors."""
        mp = self.orch.create_mission("end-to-end route and complete")

        mock_router = AsyncMock()
        mock_router.route.return_value = MagicMock(
            selected_provider="anthropic",
            selected_model="claude-sonnet-4-5",
            route_reason="ok",
            fallback_used=False,
            cost_estimate_usd=0.01,
            latency_ms=100,
            logs=MagicMock(warnings=[], errors=[]),
        )
        obs_instance = MagicMock()
        obs_cls = MagicMock(return_value=obs_instance)

        with (
            patch("orchestrator_core_under_test.ChromaticRouter", return_value=mock_router),
            patch("router.observability.ObservabilityLogger", obs_cls),
        ):
            route_result = await self.orch.route_to_provider(mp, task_type="planning")
            self.orch.complete_mission(
                mp,
                model=route_result["model"],
                role="worker",
                files_touched=[],
                result="task_result",
            )

        obs_instance._log_agent_run.assert_called_once()


# ---------------------------------------------------------------------------
# Edge cases and parametrize coverage
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def setup_method(self):
        self._mag_orch_cls = MagicMock()
        self._mag_orch_inst = MagicMock()
        self._mag_orch_inst.registered_magnets.return_value = ["scope_magnet", "security_magnet"]
        self._mag_orch_cls.return_value = self._mag_orch_inst
        self._patcher = patch("orchestrator_core_under_test.MagnetOrchestrator", self._mag_orch_cls)
        self._patcher.start()
        self.orch = Orchestrator()

    def teardown_method(self):
        self._patcher.stop()

    @pytest.mark.parametrize(
        "intent",
        [
            "",
            "a" * 1000,
            "intent with 'quotes' and \"double\" quotes",
            "intent\nwith\nnewlines",
            "unicode: 日本語 テスト",
        ],
    )
    def test_create_mission_accepts_any_intent_string(self, intent):
        mp = self.orch.create_mission(intent)
        assert mp.objective == intent

    @pytest.mark.parametrize("confidence_val", [0.0, 50.0, 75.0, 90.0, 100.0])
    def test_create_mission_from_task_confidence_roundtrip(self, confidence_val):
        mp = self.orch.create_mission_from_task({"title": "t", "confidence_required": confidence_val})
        assert mp.confidence_required == confidence_val

    @pytest.mark.parametrize("budget,level", [(0, "L1"), (20, "L1"), (21, "L2"), (999, "L2")])
    def test_autonomy_level_boundary_parametrize(self, budget, level):
        mp = self.orch.create_mission_from_task({"title": "t", "tool_budget": budget})
        assert mp.autonomy_level == level

    def test_dispatch_with_l2_mission(self):
        mp = self.orch.create_mission_from_task({"title": "big", "tool_budget": 100})
        result = self.orch.dispatch(mp)
        assert result["status"] == "ready_for_runtime"

    def test_attach_magnets_with_empty_metadata_mission(self):
        mp = _make_mission()
        result = self.orch.attach_magnets(mp)
        assert isinstance(result, list)

    def test_create_mission_from_task_none_allowed_files_treated_as_empty(self):
        """allowed_files=None must be treated like empty list — no filesystem.write."""
        mp = self.orch.create_mission_from_task({"title": "t", "allowed_files": None})
        assert "filesystem.write" not in mp.allowed_tools

    def test_create_mission_from_task_stop_conditions_is_a_copy(self):
        """Mutations to the task dict's stop_conditions must not affect the MissionPacket."""
        original = ["stop_a", "stop_b"]
        task = {"title": "t", "stop_conditions": original}
        mp = self.orch.create_mission_from_task(task)
        task["stop_conditions"].append("stop_c")
        # MissionPacket captured a copy via list()
        assert "stop_c" not in mp.stop_conditions

    @pytest.mark.asyncio
    async def test_verify_scope_no_baseline_count_key_uses_zero(self):
        """Omitting baseline_count in baseline dict must default to 0."""
        mock_result = MagicMock(passed=True, violations=[], new_files=[], modified_outside=[])
        mock_enforcer = AsyncMock()
        mock_enforcer.enforce_and_log.return_value = mock_result

        captured = []

        class CapturingScopeBaseline:
            def __init__(self, **kw):
                captured.append(kw)

        with (
            patch("scope.enforcer.ScopeEnforcer", return_value=mock_enforcer),
            patch("scope.enforcer.ScopeBaseline", CapturingScopeBaseline),
        ):
            orch = self.orch
            mp = _make_mission()
            await orch.verify_scope_after_work(mp, baseline={"expected_scope": "src/"})

        assert captured[0]["baseline_count"] == 0
