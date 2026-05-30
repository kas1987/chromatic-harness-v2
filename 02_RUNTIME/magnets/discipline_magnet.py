"""Discipline Magnet — Karpathy 4-pillar runtime scoring for implementation telemetry."""

from __future__ import annotations

from typing import Any

from .base_magnet import BaseMagnet, MagnetEvent


class DisciplineMagnet(BaseMagnet):
    name = "discipline_magnet"

    def observe(
        self,
        mission_id: str,
        inflection_point: str,
        signal: dict[str, Any],
    ) -> MagnetEvent:
        event = super().observe(mission_id, inflection_point, signal)

        read_paths: list[str] = list(signal.get("read_paths") or [])
        modified_paths: list[str] = list(signal.get("modified_paths") or [])
        expected_paths: list[str] = list(signal.get("expected_paths") or [])
        has_success_criteria = bool(signal.get("has_success_criteria"))
        assumptions_stated = bool(signal.get("assumptions_stated"))
        verification_ran = bool(signal.get("verification_ran"))
        max_lines_hint = signal.get("max_lines_hint")
        lines_changed = int(signal.get("lines_changed") or 0)

        risk = 0.0
        confidence = 0.0
        evidence: list[str] = []

        read_set = set(read_paths)
        for path in modified_paths:
            if path not in read_set:
                risk += 0.2
                evidence.append(f"WRITE without READ: {path}")

        if not assumptions_stated and inflection_point in ("pre_implementation", "discipline_check"):
            risk += 0.08
            evidence.append("Assumptions not stated (Think Before Coding)")

        if not has_success_criteria:
            risk += 0.1
            evidence.append("No verifiable success criteria (Goal-Driven Execution)")

        if modified_paths and not verification_ran and inflection_point == "post_implementation":
            risk += 0.12
            evidence.append("Success criteria not verified with tests/checks")

        if expected_paths:
            for path in modified_paths:
                if path not in expected_paths:
                    risk += 0.15
                    evidence.append(f"UNEXPECTED change: {path}")
            if len(modified_paths) > len(expected_paths) + 1:
                risk += 0.1
                evidence.append(
                    f"SCOPE CREEP: {len(modified_paths)} files vs ~{len(expected_paths)} expected"
                )

        if max_lines_hint is not None and lines_changed > int(max_lines_hint):
            risk += 0.15
            evidence.append(
                f"OVERSIZED diff: {lines_changed} lines (hint max {max_lines_hint}) — Simplicity First"
            )

        bad = {e for e in evidence if not e.startswith("Surgical")}
        if modified_paths and not bad and has_success_criteria and verification_ran:
            confidence += 0.12
            evidence.append("Karpathy discipline: read-first, scoped, verified")

        event.risk_delta = round(min(risk, 1.0), 3)
        event.confidence_delta = round(confidence, 3)
        event.evidence = evidence
        if risk >= 0.3:
            event.recommended_action = "halt_and_review"
        elif risk >= 0.15:
            event.recommended_action = "narrow_scope"
        elif confidence > 0:
            event.recommended_action = "proceed"
        return event
