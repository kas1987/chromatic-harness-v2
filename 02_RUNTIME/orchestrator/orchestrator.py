"""Chromatic Harness v2 orchestrator skeleton."""

import sys
import os
import uuid
from dataclasses import dataclass, field
from typing import Any

# Allow router imports when loaded via importlib
_HERE = os.path.dirname(os.path.abspath(__file__))
_RUNTIME = os.path.dirname(_HERE)
_REPO = os.path.dirname(_RUNTIME)
sys.path.insert(0, _REPO)
sys.path.insert(0, _RUNTIME)

from scope.guard import DispatchGuard  # noqa: E402
from magnets.base_magnet import MagnetEvent  # noqa: E402
from magnets.magnet_orchestrator import MagnetOrchestrator  # noqa: E402
from router.router import ChromaticRouter  # noqa: E402
from router.contracts import RouteRequest, RouteInput, RouteConstraints, TaskType  # noqa: E402
from router.contracts import PrivacyClass  # noqa: E402


@dataclass
class MissionPacket:
    mission_id: str
    objective: str
    agent_role: str
    autonomy_level: str
    confidence_required: float
    allowed_tools: list[str]
    stop_conditions: list[str]
    required_outputs: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


class Orchestrator:
    def create_mission(self, intent: str) -> MissionPacket:
        return MissionPacket(
            mission_id=f"CHR-MISSION-{str(uuid.uuid4())[:8].upper()}",
            objective=intent,
            agent_role="agent_lead",
            autonomy_level="L1",
            confidence_required=75,
            allowed_tools=["filesystem.read"],
            stop_conditions=[
                "confidence_below_threshold",
                "scope_unclear",
                "security_risk_detected",
            ],
            required_outputs=["agent_lead_report", "next_bead"],
        )

    def create_mission_from_task(self, task: dict[str, Any]) -> MissionPacket:
        """Build a mission packet from a workflow task-graph node or CLI task dict."""
        title = task.get("title") or task.get("objective", "")
        allowed_files = task.get("allowed_files") or []
        confidence_required = float(task.get("confidence_required", task.get("confidence_score", 75)))
        stop_conditions = list(
            task.get(
                "stop_conditions",
                [
                    "confidence_below_threshold",
                    "scope_unclear",
                    "security_risk_detected",
                ],
            )
        )
        role = task.get("role", "worker")
        tool_budget = task.get("tool_budget", 0)
        allowed_tools = ["filesystem.read"]
        if allowed_files:
            allowed_tools.append("filesystem.write")
        return MissionPacket(
            mission_id=f"CHR-MISSION-{str(uuid.uuid4())[:8].upper()}",
            objective=title,
            agent_role=role,
            autonomy_level="L2" if tool_budget > 20 else "L1",
            confidence_required=confidence_required,
            allowed_tools=allowed_tools,
            stop_conditions=stop_conditions,
            required_outputs=["task_result", "verifier_report"],
            metadata={
                "task_id": task.get("task_id", ""),
                "assigned_model": task.get("assigned_model", ""),
                "allowed_files": allowed_files,
                "tool_budget": tool_budget,
                "bead_id": task.get("bead_id", ""),
            },
        )

    def attach_magnets(self, mission: MissionPacket) -> list[str]:
        return MagnetOrchestrator().registered_magnets()

    def synthesize_mission(
        self,
        mission: MissionPacket,
        events: list[MagnetEvent | dict],
    ):
        """Run magnet pipeline + Agent Lead synthesis on mission events."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("agent_lead", os.path.join(_HERE, "agent_lead.py"))
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules["agent_lead"] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        AgentLead = mod.AgentLead

        orchestrator = MagnetOrchestrator()
        report = orchestrator.process(mission.mission_id, events)
        lead = AgentLead(orchestrator)
        return lead.run(mission.__dict__, events, report)

    async def guard_and_inject(
        self,
        mission: MissionPacket,
        *,
        file_scope: str = "",
        agent_id: str = "chromatic_orchestrator",
    ) -> dict[str, Any]:
        """Inject system memory context and record scope baseline before dispatch."""
        guard = DispatchGuard()
        guarded = await guard.guard(
            mission.__dict__,
            file_scope=file_scope,
            agent_id=agent_id,
        )
        # Merge injected context back into mission
        mission.metadata.update(guarded.mission.get("metadata", {}))
        return {
            "mission_id": mission.mission_id,
            "status": "guarded_and_ready",
            "scope_baseline": {
                "expected_scope": guarded.scope_baseline.expected_scope if guarded.scope_baseline else "",
                "baseline_count": guarded.scope_baseline.baseline_count if guarded.scope_baseline else 0,
            },
            "injected_rules": [r["name"] for r in guarded.injected_context.get("governance_rules", [])],
            "scope_header_present": bool(guarded.scope_header),
        }

    async def verify_scope_after_work(
        self,
        mission: MissionPacket,
        baseline: dict[str, Any],
    ) -> dict[str, Any]:
        """Post-work scope verification. Must run before marking mission complete."""
        from scope.enforcer import ScopeEnforcer, ScopeBaseline

        if not baseline.get("expected_scope"):
            return {"passed": True, "reason": "no_scope_declared"}
        enforcer = ScopeEnforcer()
        sb = ScopeBaseline(
            mission_id=mission.mission_id,
            expected_scope=baseline["expected_scope"],
            baseline_count=baseline.get("baseline_count", 0),
        )
        result = await enforcer.enforce_and_log(sb, task_id=mission.mission_id)
        return {
            "passed": result.passed,
            "violations": result.violations,
            "new_files_outside_scope": result.new_files,
            "modified_outside_scope": result.modified_outside,
        }

    async def route_to_provider(
        self,
        mission: MissionPacket,
        *,
        task_type: str = "planning",
    ) -> dict[str, Any]:
        """Route a mission through ChromaticRouter and return provider selection."""
        router = ChromaticRouter()
        req = RouteRequest(
            task_id=mission.mission_id,
            task_type=TaskType(task_type),
            objective=mission.objective,
            input=RouteInput(messages=[], files=[], metadata=mission.metadata),
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P1,
                max_cost_usd=0.25,
            ),
        )
        resp = await router.route(req)
        return {
            "provider": resp.selected_provider,
            "model": resp.selected_model,
            "reason": resp.route_reason,
            "fallback_used": resp.fallback_used,
            "cost_estimate_usd": resp.cost_estimate_usd,
            "latency_ms": int(resp.latency_ms),
            "warnings": resp.logs.warnings,
            "errors": resp.logs.errors,
        }

    def dispatch(self, mission: MissionPacket) -> dict[str, Any]:
        return {
            "mission_id": mission.mission_id,
            "status": "ready_for_runtime",
            "magnets": self.attach_magnets(mission),
        }

    def complete_mission(
        self,
        mission: MissionPacket,
        *,
        model: str,
        role: str,
        files_touched: list[str],
        result: str,
        validation: str = "",
        next_task: str = "",
        tools_used: int = 0,
    ) -> None:
        """Append a PDR-GOV-SONNET-KIMI-001 completion record to AGENT_RUN_LOG.jsonl.

        Call this after the agent finishes its work — the router dispatch logs
        the routing decision; this logs the post-run outcome.
        """
        from router.confidence import ConfidenceGate
        from router.contracts import ConfidenceBand, RouteConfidence
        from router.observability import ObservabilityLogger

        band = ConfidenceGate.band_from_score(mission.confidence_required)
        logger = ObservabilityLogger()

        # Build minimal stubs so _log_agent_run can read req.task_id and
        # req.confidence.band without needing a full RouteRequest.
        class _FakeConf:
            def __init__(self, b: ConfidenceBand, s: float):
                self.band = b
                self.score = s

        class _FakeReq:
            def __init__(self, tid: str, conf: _FakeConf):
                self.task_id = tid
                self.confidence = conf

        class _FakeType:
            def __init__(self, v: str):
                self.value = v

        class _FakeOutput:
            def __init__(self, v: str):
                self.type = _FakeType(v)

        class _FakeResp:
            def __init__(self, m: str, s: float, out: _FakeOutput):
                self.selected_model = m
                self.confidence_score = s
                self.output = out

        fake_req = _FakeReq(mission.mission_id, _FakeConf(band, mission.confidence_required))
        fake_resp = _FakeResp(model, mission.confidence_required, _FakeOutput(result))
        logger._log_agent_run(
            fake_req,  # type: ignore[arg-type]
            fake_resp,  # type: ignore[arg-type]
            extra={
                "role": role,
                "tools_used": tools_used,
                "files_touched": files_touched,
                "validation": validation,
                "next_task": next_task,
            },
        )
