"""Plan Magnet — observes plan quality at the PLAN & DECOMPOSE inflection point.

Canonical magnet #2 in the harness pipeline (INTAKE → PLAN → DISPATCH → EXECUTION
→ VALIDATION → DECISION → CLOSURE). Captures plan quality, decomposition check,
graph validation, and tool feasibility from planning telemetry.
"""

from __future__ import annotations

from typing import Any

from .base_magnet import BaseMagnet, MagnetEvent

_PLAN_POINTS = {"plan", "post_plan", "decompose", "plan_decompose"}


class PlanMagnet(BaseMagnet):
    name = "plan_magnet"

    def observe(
        self, mission_id: str, inflection_point: str, signal: dict[str, Any]
    ) -> MagnetEvent:
        event = super().observe(mission_id, inflection_point, signal)
        if inflection_point not in _PLAN_POINTS:
            return event

        plan_steps: list[Any] = list(signal.get("plan_steps") or [])
        subtasks: list[Any] = list(signal.get("subtasks") or [])
        tool_requirements: list[str] = list(signal.get("tool_requirements") or [])
        available_tools: list[str] = list(signal.get("available_tools") or [])
        graph_edges: list[Any] = list(signal.get("graph_edges") or [])

        risk = 0.0
        confidence = 0.0
        evidence: list[str] = []

        # Plan quality — a plan must have concrete steps
        if not plan_steps:
            risk += 0.15
            evidence.append("No plan steps provided (plan quality)")
        elif any(not str(s).strip() for s in plan_steps):
            risk += 0.05
            evidence.append("Plan contains empty steps")
        else:
            confidence += 0.05

        # Decomposition check — flag missing or runaway decomposition
        if not subtasks:
            risk += 0.1
            evidence.append("No decomposition into subtasks")
        elif len(subtasks) > 50:
            risk += 0.1
            evidence.append(f"Excessive decomposition: {len(subtasks)} subtasks")
        else:
            confidence += 0.05

        # Graph validation — edges must reference known nodes and be acyclic
        if graph_edges:
            graph_risk, graph_evidence = self._validate_graph(subtasks, graph_edges)
            risk += graph_risk
            evidence.extend(graph_evidence)
            if not graph_evidence:
                confidence += 0.05

        # Tool feasibility — required tools must be in the allowlist
        if tool_requirements:
            if not available_tools:
                risk += 0.08
                evidence.append("Tool requirements declared but no tools available")
            else:
                missing = [t for t in tool_requirements if t not in available_tools]
                if missing:
                    risk += min(len(missing) * 0.1, 0.4)
                    evidence.append(f"Infeasible tools: {', '.join(missing)}")
                else:
                    confidence += 0.05

        event.risk_delta = round(min(risk, 1.0), 3)
        event.confidence_delta = round(confidence, 3)
        event.evidence = evidence
        if risk >= 0.3:
            event.recommended_action = "replan"
        elif risk >= 0.15:
            event.recommended_action = "refine_plan"
        elif confidence > 0:
            event.recommended_action = "proceed"
        return event

    @staticmethod
    def _validate_graph(
        subtasks: list[Any], graph_edges: list[Any]
    ) -> tuple[float, list[str]]:
        """Detect dangling edges and cycles in the execution graph."""
        evidence: list[str] = []
        risk = 0.0

        nodes = {str(i) for i in range(len(subtasks))}
        nodes |= {
            str(s.get("id"))
            for s in subtasks
            if isinstance(s, dict) and s.get("id") is not None
        }

        adjacency: dict[str, list[str]] = {}
        for edge in graph_edges:
            try:
                src, dst = (
                    (str(edge[0]), str(edge[1]))
                    if isinstance(edge, (list, tuple))
                    else (
                        str(edge.get("from")),
                        str(edge.get("to")),
                    )
                )
            except (IndexError, KeyError, AttributeError, TypeError):
                evidence.append(f"Malformed graph edge: {edge!r}")
                risk += 0.05
                continue
            if nodes and (src not in nodes or dst not in nodes):
                evidence.append(f"Dangling edge: {src}->{dst}")
                risk += 0.05
            adjacency.setdefault(src, []).append(dst)

        if PlanMagnet._has_cycle(adjacency):
            evidence.append("Execution graph contains a cycle")
            risk += 0.2

        return risk, evidence

    @staticmethod
    def _has_cycle(adjacency: dict[str, list[str]]) -> bool:
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {n: WHITE for n in adjacency}

        def visit(node: str) -> bool:
            color[node] = GRAY
            for nxt in adjacency.get(node, []):
                state = color.get(nxt, WHITE)
                if state == GRAY:
                    return True
                if state == WHITE and visit(nxt):
                    return True
            color[node] = BLACK
            return False

        return any(color.get(n, WHITE) == WHITE and visit(n) for n in list(adjacency))
