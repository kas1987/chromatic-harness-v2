"""Magnet pipeline coordinator: COLLECT → NORMALIZE → CORRELATE → SCORE → FEEDBACK → RECOMMEND."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base_magnet import MagnetEvent
from .closure_magnet import ClosureMagnet
from .confidence_magnet import ConfidenceMagnet
from .cost_magnet import CostMagnet
from .execution_magnet import ExecutionMagnet
from .intake_magnet import IntakeMagnet
from .intent_magnet import IntentMagnet
from .memory_magnet import MemoryMagnet
from .scope_magnet import ScopeMagnet
from .security_magnet import SecurityMagnet
from .validation_magnet import ValidationMagnet


@dataclass
class NormalizedEvent:
    mission_id: str
    magnet_name: str
    inflection_point: str
    risk_delta: float
    confidence_delta: float
    recommended_action: str
    evidence: list[str]
    signal_keys: list[str]


@dataclass
class MagnetReport:
    mission_id: str
    collected_count: int
    normalized: list[NormalizedEvent]
    correlated: dict[str, Any]
    score: float
    confidence_score: float
    risk_score: float
    feedback: list[str]
    recommendation: str
    gold_artifact: dict[str, Any] = field(default_factory=dict)


class MagnetOrchestrator:
    """Runs the six-stage magnet feedback pipeline on a batch of events."""

    def __init__(self) -> None:
        self._magnets = {
            m.name: m
            for m in (
                IntakeMagnet(),
                IntentMagnet(),
                ScopeMagnet(),
                ExecutionMagnet(),
                CostMagnet(),
                ConfidenceMagnet(),
                ValidationMagnet(),
                MemoryMagnet(),
                SecurityMagnet(),
                ClosureMagnet(),
            )
        }

    def registered_magnets(self) -> list[str]:
        return sorted(self._magnets.keys())

    def observe(
        self, mission_id: str, magnet_name: str, inflection_point: str, signal: dict
    ) -> MagnetEvent:
        magnet = self._magnets.get(magnet_name)
        if magnet is None:
            magnet = self._magnets["intent_magnet"]
        return magnet.observe(mission_id, inflection_point, signal)

    def process(
        self, mission_id: str, events: list[MagnetEvent | dict[str, Any]]
    ) -> MagnetReport:
        collected = self._collect(mission_id, events)
        normalized = self._normalize(collected)
        correlated = self._correlate(normalized)
        score, confidence_score, risk_score = self._score(correlated)
        feedback = self._feedback(normalized, correlated, score)
        recommendation = self._recommend(score, risk_score, feedback)
        return MagnetReport(
            mission_id=mission_id,
            collected_count=len(collected),
            normalized=normalized,
            correlated=correlated,
            score=score,
            confidence_score=confidence_score,
            risk_score=risk_score,
            feedback=feedback,
            recommendation=recommendation,
            gold_artifact={
                "mission_id": mission_id,
                "score": score,
                "confidence_score": confidence_score,
                "risk_score": risk_score,
                "recommendation": recommendation,
                "feedback": feedback,
                "correlated": correlated,
            },
        )

    def _collect(
        self, mission_id: str, events: list[MagnetEvent | dict[str, Any]]
    ) -> list[MagnetEvent]:
        out: list[MagnetEvent] = []
        for item in events:
            if isinstance(item, MagnetEvent):
                out.append(item)
                continue
            out.append(
                MagnetEvent(
                    mission_id=item.get("mission_id", mission_id),
                    magnet_name=item.get("magnet_name", "unknown"),
                    inflection_point=item.get("inflection_point", "unknown"),
                    observed_signal=item.get("observed_signal", {}),
                    risk_delta=float(item.get("risk_delta", 0.0)),
                    confidence_delta=float(item.get("confidence_delta", 0.0)),
                    evidence=list(item.get("evidence", [])),
                    recommended_action=item.get("recommended_action", "none"),
                    event_id=item.get("event_id", ""),
                    timestamp=item.get("timestamp", ""),
                )
            )
        return out

    def _normalize(self, events: list[MagnetEvent]) -> list[NormalizedEvent]:
        return [
            NormalizedEvent(
                mission_id=e.mission_id,
                magnet_name=e.magnet_name,
                inflection_point=e.inflection_point,
                risk_delta=e.risk_delta,
                confidence_delta=e.confidence_delta,
                recommended_action=e.recommended_action,
                evidence=list(e.evidence),
                signal_keys=sorted(e.observed_signal.keys()),
            )
            for e in events
        ]

    def _correlate(self, events: list[NormalizedEvent]) -> dict[str, Any]:
        if not events:
            return {
                "event_count": 0,
                "magnets_seen": [],
                "inflection_points": [],
                "total_risk_delta": 0.0,
                "total_confidence_delta": 0.0,
                "halt_actions": 0,
                "escalations": 0,
            }
        magnets = sorted({e.magnet_name for e in events})
        inflections = sorted({e.inflection_point for e in events})
        halt_actions = sum(
            1
            for e in events
            if e.recommended_action in ("halt_and_revert", "halt", "escalate")
        )
        escalations = sum(
            1 for e in events if e.recommended_action in ("escalate", "review")
        )
        return {
            "event_count": len(events),
            "magnets_seen": magnets,
            "inflection_points": inflections,
            "total_risk_delta": round(sum(e.risk_delta for e in events), 4),
            "total_confidence_delta": round(sum(e.confidence_delta for e in events), 4),
            "halt_actions": halt_actions,
            "escalations": escalations,
            "evidence_items": [ev for e in events for ev in e.evidence],
        }

    def _score(self, correlated: dict[str, Any]) -> tuple[float, float, float]:
        base = 75.0 + correlated.get("total_confidence_delta", 0.0)
        risk = max(0.0, correlated.get("total_risk_delta", 0.0))
        confidence_score = max(0.0, min(100.0, base - risk * 10))
        risk_score = min(1.0, risk)
        score = round(confidence_score - risk_score * 20, 2)
        return score, round(confidence_score, 2), round(risk_score, 4)

    def _feedback(
        self,
        normalized: list[NormalizedEvent],
        correlated: dict[str, Any],
        score: float,
    ) -> list[str]:
        notes: list[str] = []
        if correlated.get("event_count", 0) == 0:
            notes.append("No magnet events recorded for this mission.")
        if correlated.get("halt_actions", 0) > 0:
            notes.append(
                f"{correlated['halt_actions']} halt/escalate action(s) detected."
            )
        if correlated.get("total_risk_delta", 0.0) > 0.3:
            notes.append("Elevated cumulative risk delta across magnets.")
        if score < 60:
            notes.append("Composite score below replan threshold.")
        elif score >= 90:
            notes.append("High-confidence mission; safe to auto-proceed.")
        security_events = [e for e in normalized if e.magnet_name == "security_magnet"]
        if security_events:
            notes.append(f"{len(security_events)} security magnet event(s) logged.")
        return notes

    def _recommend(self, score: float, risk_score: float, feedback: list[str]) -> str:
        if any("No magnet events" in f for f in feedback):
            return "review"
        if risk_score >= 0.5 or any("halt" in f.lower() for f in feedback):
            return "halt"
        if score >= 90:
            return "proceed"
        if score >= 75:
            return "proceed_reversible_only"
        if score >= 60:
            return "replan"
        return "review"
