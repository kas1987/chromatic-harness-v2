"""Confidence scoring and band assignment for routing decisions."""

from .contracts import ConfidenceBand, RouteRequest, RouteLogs


class ConfidenceGate:
    """Evaluates whether a route request is safe to execute."""

    @staticmethod
    def band_from_score(score: float) -> ConfidenceBand:
        if score >= 90:
            return ConfidenceBand.VERY_HIGH
        if score >= 75:
            return ConfidenceBand.HIGH
        if score >= 60:
            return ConfidenceBand.MEDIUM
        if score >= 40:
            return ConfidenceBand.LOW
        return ConfidenceBand.BLOCKED

    @staticmethod
    def score(inputs: dict[str, float]) -> float:
        return round(
            inputs.get("objective_clarity", 0.0) * 0.20
            + inputs.get("provider_fit", 0.0) * 0.20
            + inputs.get("privacy_risk_clarity", 0.0) * 0.15
            + inputs.get("cost_fit", 0.0) * 0.15
            + inputs.get("context_sufficiency", 0.0) * 0.15
            + inputs.get("reversibility", 0.0) * 0.10
            + inputs.get("testability", 0.0) * 0.05,
            2,
        )

    def check(self, req: RouteRequest) -> tuple[bool, RouteLogs]:
        logs = RouteLogs()
        score = req.confidence.score
        band = req.confidence.band

        if band == ConfidenceBand.BLOCKED or score < 60:
            logs.errors.append(f"Confidence {score}/{band.value} < 60. Halting external route.")
            return False, logs

        logs.policy_checks.append(f"Confidence gate passed: {score} ({band.value}).")
        return True, logs
