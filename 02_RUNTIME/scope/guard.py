"""Pre-dispatch guard: injects memory context and scope headers into missions.

Runs before any worker/agent receives a task. Ensures:
1. Governance rules are injected into the prompt context.
2. FILE SCOPE baseline is recorded before dispatch.
3. Session continuity memory is attached.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_RUNTIME = _HERE.parent
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from memory.store import SystemMemoryStore
from scope.enforcer import ScopeEnforcer, ScopeBaseline


@dataclass
class GuardedMission:
    mission: dict[str, Any]
    scope_baseline: ScopeBaseline | None
    injected_context: dict[str, Any]
    scope_header: str


class DispatchGuard:
    """Wraps mission dispatch with memory injection and scope capture."""

    def __init__(self, repo_root: str | None = None):
        self.memory = SystemMemoryStore()
        self.enforcer = ScopeEnforcer(repo_root)

    async def guard(
        self,
        mission: dict[str, Any],
        *,
        file_scope: str = "",
        agent_id: str = "unknown",
    ) -> GuardedMission:
        mission_id = mission.get("mission_id", "")

        # 1. Assemble relevant memory context
        mission_type = mission.get("objective", "")[:50]
        privacy_class = mission.get("privacy_class", "P1")
        context = await self.memory.assemble_context(
            mission_type=mission_type,
            privacy_class=privacy_class,
            include_rules=["file_scope", "security", "privacy", "routing"],
        )

        # 2. Take scope baseline if scope declared
        baseline = None
        if file_scope:
            baseline = self.enforcer.take_baseline(mission_id, file_scope)

        # 3. Build scope header
        rules = context.get("governance_rules", [])
        scope_header = self.enforcer.build_scope_header(file_scope, rules)

        # 4. Attach injected context to mission metadata
        mission["metadata"] = mission.get("metadata", {})
        mission["metadata"]["chromatic_context"] = context
        mission["metadata"]["chromatic_scope_header"] = scope_header
        mission["metadata"]["chromatic_scope_baseline"] = {
            "mission_id": baseline.mission_id if baseline else "",
            "expected_scope": baseline.expected_scope if baseline else "",
            "baseline_count": baseline.baseline_count if baseline else 0,
        } if baseline else {}

        # 5. Record session start
        await self.memory.start_session(
            agent_id=agent_id,
            project_context={
                "mission_id": mission_id,
                "file_scope": file_scope,
                "objective": mission.get("objective", ""),
            },
        )

        return GuardedMission(
            mission=mission,
            scope_baseline=baseline,
            injected_context=context,
            scope_header=scope_header,
        )
