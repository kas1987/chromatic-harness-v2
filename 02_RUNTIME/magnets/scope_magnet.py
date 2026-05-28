"""Scope Magnet — observes file-system boundary violations during agent execution.

Integrates with the ScopeEnforcer to detect, log, and escalate scope creep.
"""

from __future__ import annotations

import sys
from typing import Any
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_RUNTIME = _HERE.parent
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent
from scope.enforcer import ScopeEnforcer
from memory.store import SystemMemoryStore


class ScopeMagnet(BaseMagnet):
    name = "scope_magnet"

    def __init__(self) -> None:
        self.enforcer: ScopeEnforcer | None = None
        self._store = SystemMemoryStore()

    def observe(
        self,
        mission_id: str,
        inflection_point: str,
        signal: dict[str, Any],
    ) -> MagnetEvent:
        event = super().observe(mission_id, inflection_point, signal)

        # Detect scope violation signals from execution telemetry
        if inflection_point == "post_execution" and signal.get("file_scope"):
            expected_scope = signal["file_scope"]
            # If baseline was recorded, run enforcement
            baseline_data = signal.get("scope_baseline")
            if baseline_data and baseline_data.get("expected_scope"):
                from ..scope.enforcer import ScopeBaseline
                baseline = ScopeBaseline(
                    mission_id=mission_id,
                    expected_scope=baseline_data["expected_scope"],
                    baseline_count=baseline_data.get("baseline_count", 0),
                )
                import asyncio
                result = asyncio.get_event_loop().run_until_complete(
                    self.enforcer.enforce_and_log(baseline, task_id=mission_id)
                    if self.enforcer
                    else self._default_enforcer().enforce_and_log(baseline, task_id=mission_id)
                )
                if not result.passed:
                    event.risk_delta = min(len(result.violations) * 0.15, 1.0)
                    event.recommended_action = "halt_and_revert"
                    event.evidence = result.violations
        return event

    def _default_enforcer(self) -> ScopeEnforcer:
        if self.enforcer is None:
            self.enforcer = ScopeEnforcer()
        return self.enforcer
