"""Tests for ConfidenceGate: band classification, score calculation, gate check."""

from __future__ import annotations

import pytest

from router.confidence import ConfidenceGate
from router.contracts import (
    ConfidenceBand,
    RouteConfidence,
    RouteRequest,
    RouteInput,
    RouteConstraints,
    RouteAudit,
    TaskType,
    PrivacyClass,
)


def _make_req(score: float, band: ConfidenceBand | None = None) -> RouteRequest:
    b = band or ConfidenceGate.band_from_score(score)
    return RouteRequest(
        request_id="r-1",
        task_id="t-1",
        task_type=TaskType.CLASSIFICATION,
        objective="test",
        confidence=RouteConfidence(score=score, band=b),
        constraints=RouteConstraints(privacy_class=PrivacyClass.P1),
        audit=RouteAudit(),
    )


# ── band_from_score ──────────────────────────────────────────────────────────


class TestBandFromScore:
    def test_very_high_at_90(self):
        assert ConfidenceGate.band_from_score(90.0) == ConfidenceBand.VERY_HIGH

    def test_very_high_at_100(self):
        assert ConfidenceGate.band_from_score(100.0) == ConfidenceBand.VERY_HIGH

    def test_very_high_at_95(self):
        assert ConfidenceGate.band_from_score(95.0) == ConfidenceBand.VERY_HIGH

    def test_high_at_89(self):
        assert ConfidenceGate.band_from_score(89.9) == ConfidenceBand.HIGH

    def test_high_at_75(self):
        assert ConfidenceGate.band_from_score(75.0) == ConfidenceBand.HIGH

    def test_medium_at_74(self):
        assert ConfidenceGate.band_from_score(74.9) == ConfidenceBand.MEDIUM

    def test_medium_at_60(self):
        assert ConfidenceGate.band_from_score(60.0) == ConfidenceBand.MEDIUM

    def test_low_at_59(self):
        assert ConfidenceGate.band_from_score(59.9) == ConfidenceBand.LOW

    def test_low_at_40(self):
        assert ConfidenceGate.band_from_score(40.0) == ConfidenceBand.LOW

    def test_blocked_at_39(self):
        assert ConfidenceGate.band_from_score(39.9) == ConfidenceBand.BLOCKED

    def test_blocked_at_zero(self):
        assert ConfidenceGate.band_from_score(0.0) == ConfidenceBand.BLOCKED

    def test_blocked_at_negative(self):
        assert ConfidenceGate.band_from_score(-10.0) == ConfidenceBand.BLOCKED

    # Boundary: score exactly at boundary belongs to the higher band
    def test_boundary_90_is_very_high(self):
        assert ConfidenceGate.band_from_score(90.0) == ConfidenceBand.VERY_HIGH

    def test_boundary_75_is_high(self):
        assert ConfidenceGate.band_from_score(75.0) == ConfidenceBand.HIGH

    def test_boundary_60_is_medium(self):
        assert ConfidenceGate.band_from_score(60.0) == ConfidenceBand.MEDIUM

    def test_boundary_40_is_low(self):
        assert ConfidenceGate.band_from_score(40.0) == ConfidenceBand.LOW


# ── score calculation ────────────────────────────────────────────────────────


class TestScoreCalculation:
    def test_all_zeros_returns_zero(self):
        s = ConfidenceGate.score({})
        assert s == 0.0

    def test_all_max_inputs(self):
        inputs = {
            "objective_clarity": 100.0,
            "provider_fit": 100.0,
            "privacy_risk_clarity": 100.0,
            "cost_fit": 100.0,
            "context_sufficiency": 100.0,
            "reversibility": 100.0,
            "testability": 100.0,
        }
        # Weights: 0.20 + 0.20 + 0.15 + 0.15 + 0.15 + 0.10 + 0.05 = 1.00
        result = ConfidenceGate.score(inputs)
        assert abs(result - 100.0) < 0.01

    def test_partial_inputs(self):
        inputs = {
            "objective_clarity": 80.0,
            "provider_fit": 80.0,
        }
        # 80*0.20 + 80*0.20 = 16+16 = 32
        result = ConfidenceGate.score(inputs)
        assert abs(result - 32.0) < 0.01

    def test_weights_sum(self):
        """Verify the weighting totals to 1.0 by testing all at 50."""
        inputs = {
            k: 50.0
            for k in [
                "objective_clarity",
                "provider_fit",
                "privacy_risk_clarity",
                "cost_fit",
                "context_sufficiency",
                "reversibility",
                "testability",
            ]
        }
        result = ConfidenceGate.score(inputs)
        assert abs(result - 50.0) < 0.01

    def test_missing_keys_treated_as_zero(self):
        result = ConfidenceGate.score({"objective_clarity": 100.0})
        assert result == pytest.approx(20.0, abs=0.01)

    def test_result_is_rounded_to_two_decimals(self):
        inputs = {"objective_clarity": 33.33333}
        result = ConfidenceGate.score(inputs)
        assert result == round(result, 2)


# ── check() gate ─────────────────────────────────────────────────────────────


class TestConfidenceGateCheck:
    def test_passes_at_60(self):
        gate = ConfidenceGate()
        req = _make_req(60.0)
        ok, logs = gate.check(req)
        assert ok is True
        assert any("passed" in msg.lower() for msg in logs.policy_checks)
        assert logs.errors == []

    def test_passes_at_75(self):
        gate = ConfidenceGate()
        req = _make_req(75.0)
        ok, logs = gate.check(req)
        assert ok is True

    def test_passes_at_100(self):
        gate = ConfidenceGate()
        req = _make_req(100.0)
        ok, logs = gate.check(req)
        assert ok is True

    def test_blocks_below_60(self):
        gate = ConfidenceGate()
        req = _make_req(59.9)
        ok, logs = gate.check(req)
        assert ok is False
        assert logs.errors

    def test_blocks_at_zero(self):
        gate = ConfidenceGate()
        req = _make_req(0.0)
        ok, logs = gate.check(req)
        assert ok is False
        assert any("60" in e for e in logs.errors)

    def test_blocks_negative_score(self):
        gate = ConfidenceGate()
        req = _make_req(-5.0)
        ok, logs = gate.check(req)
        assert ok is False

    def test_blocked_band_blocks_regardless_of_score(self):
        gate = ConfidenceGate()
        # Score 65 (MEDIUM) but band explicitly set to BLOCKED
        req = _make_req(65.0, band=ConfidenceBand.BLOCKED)
        ok, logs = gate.check(req)
        assert ok is False
        assert logs.errors

    def test_band_as_string_accepted(self):
        """Band from API can arrive as a plain string."""
        gate = ConfidenceGate()
        req = _make_req(70.0)
        req.confidence.band = "medium"  # type: ignore[assignment]
        ok, logs = gate.check(req)
        assert ok is True

    def test_blocked_band_string_blocks(self):
        gate = ConfidenceGate()
        req = _make_req(70.0)
        req.confidence.band = "blocked"  # type: ignore[assignment]
        ok, logs = gate.check(req)
        assert ok is False

    def test_error_message_contains_score(self):
        gate = ConfidenceGate()
        req = _make_req(42.0)
        ok, logs = gate.check(req)
        assert ok is False
        assert any("42" in e or "42.0" in e for e in logs.errors)

    def test_pass_message_contains_score_and_band(self):
        gate = ConfidenceGate()
        req = _make_req(80.0)
        ok, logs = gate.check(req)
        assert ok is True
        assert any("80" in msg for msg in logs.policy_checks)
