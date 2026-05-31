"""Dispatch Magnet — observes the DISPATCH inflection point before execution.

Canonical magnet #3. Verifies an agent is assigned, scope & budget are set, the
tool allowlist is locked, and a pre-execution state snapshot was captured. This is
the last gate before agents touch the environment, so missing controls are scored
as elevated risk.
"""

from __future__ import annotations

from typing import Any

from .base_magnet import BaseMagnet, MagnetEvent

_DISPATCH_POINTS = {"dispatch", "pre_execution", "assign"}


class DispatchMagnet(BaseMagnet):
    name = "dispatch_magnet"

    def observe(
        self, mission_id: str, inflection_point: str, signal: dict[str, Any]
    ) -> MagnetEvent:
        event = super().observe(mission_id, inflection_point, signal)
        if inflection_point not in _DISPATCH_POINTS:
            return event

        agent = signal.get("agent") or signal.get("assigned_agent")
        allowed_tools: list[str] = list(signal.get("allowed_tools") or [])
        budget = signal.get("budget")
        file_scope: list[str] = list(signal.get("file_scope") or [])
        state_snapshot = signal.get("state_snapshot")

        risk = 0.0
        confidence = 0.0
        evidence: list[str] = []

        # Agent assigned
        if not agent:
            risk += 0.15
            evidence.append("No agent assigned for dispatch")
        else:
            confidence += 0.05

        # Tool allowlist locked
        if not allowed_tools:
            risk += 0.12
            evidence.append("Tool allowlist not locked (no allowed_tools)")
        else:
            confidence += 0.05

        # Scope set
        if not file_scope:
            risk += 0.1
            evidence.append("File scope not set before dispatch")
        else:
            confidence += 0.05

        # Budget set
        if budget is None or (isinstance(budget, (int, float)) and budget <= 0):
            risk += 0.1
            evidence.append("Budget not set for dispatch")
        else:
            confidence += 0.05

        # State snapshot captured (enables rollback)
        if not state_snapshot:
            risk += 0.08
            evidence.append("No pre-execution state snapshot (rollback unavailable)")
        else:
            confidence += 0.05

        event.risk_delta = round(min(risk, 1.0), 3)
        event.confidence_delta = round(confidence, 3)
        event.evidence = evidence
        if risk >= 0.3:
            event.recommended_action = "halt_and_review"
        elif risk >= 0.15:
            event.recommended_action = "lock_controls"
        elif confidence > 0:
            event.recommended_action = "proceed"
        return event
