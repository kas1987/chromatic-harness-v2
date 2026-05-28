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

from router.router import ChromaticRouter  # noqa: E402
from router.contracts import (  # noqa: E402
    RouteRequest,
    TaskType,
    PrivacyClass,
    RouteConstraints,
    RouteConfidence,
    RouteAudit,
    RouteInput,
)
from memory.store import SystemMemoryStore  # noqa: E402
from scope.guard import DispatchGuard  # noqa: E402


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
            stop_conditions=["confidence_below_threshold", "scope_unclear", "security_risk_detected"],
            required_outputs=["agent_lead_report", "next_bead"],
        )

    def attach_magnets(self, mission: MissionPacket) -> list[str]:
        return ["intent_magnet", "scope_magnet", "execution_magnet", "confidence_magnet", "memory_magnet"]

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

    def dispatch(self, mission: MissionPacket) -> dict[str, Any]:
        return {
            "mission_id": mission.mission_id,
            "status": "ready_for_runtime",
            "magnets": self.attach_magnets(mission),
        }

    async def route_to_provider(self, mission: MissionPacket, task_type: str = "planning") -> dict[str, Any]:
        """Route a mission objective through ChromaticRouter to select a model/provider."""
        router = ChromaticRouter()
        req = RouteRequest(
            request_id=str(uuid.uuid4()),
            task_id=mission.mission_id,
            task_type=TaskType(task_type),
            objective=mission.objective,
            input=RouteInput(),
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P1,
                allow_openhuman=False,
            ),
            confidence=RouteConfidence(
                score=mission.confidence_required,
            ),
            preferred_provider="auto",
            fallback_chain=[],
            audit=RouteAudit(caller="orchestrator"),
        )
        resp = await router.route(req)
        return {
            "provider": resp.selected_provider,
            "model": resp.selected_model,
            "reason": resp.route_reason,
            "fallback_used": resp.fallback_used,
            "cost_estimate_usd": resp.cost_estimate_usd,
            "latency_ms": resp.latency_ms,
            "warnings": resp.logs.warnings,
            "errors": resp.logs.errors,
        }
