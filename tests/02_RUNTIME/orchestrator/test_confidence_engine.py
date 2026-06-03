"""Tests for orchestrator/confidence_engine.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

_CE_PATH = _RUNTIME / "orchestrator" / "confidence_engine.py"
_spec = importlib.util.spec_from_file_location("confidence_engine_under_test", _CE_PATH)
_ce_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_ce_mod)  # type: ignore[union-attr]

ConfidenceInputs = _ce_mod.ConfidenceInputs
score_confidence = _ce_mod.score_confidence
decision_from_score = _ce_mod.decision_from_score


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _perfect() -> ConfidenceInputs:
    """All inputs at maximum (100)."""
    return ConfidenceInputs(
        objective_clarity=100.0,
        scope_clarity=100.0,
        evidence_quality=100.0,
        reversibility=100.0,
        tool_fit=100.0,
        risk_awareness=100.0,
        testability=100.0,
    )


def _zero() -> ConfidenceInputs:
    """All inputs at zero."""
    return ConfidenceInputs(
        objective_clarity=0.0,
        scope_clarity=0.0,
        evidence_quality=0.0,
        reversibility=0.0,
        tool_fit=0.0,
        risk_awareness=0.0,
        testability=0.0,
    )


def _inputs(**overrides) -> ConfidenceInputs:
    base = dict(
        objective_clarity=80.0,
        scope_clarity=80.0,
        evidence_quality=80.0,
        reversibility=80.0,
        tool_fit=80.0,
        risk_awareness=80.0,
        testability=80.0,
    )
    base.update(overrides)
    return ConfidenceInputs(**base)


# ---------------------------------------------------------------------------
# ConfidenceInputs dataclass
# ---------------------------------------------------------------------------


class TestConfidenceInputs:
    def test_fields_stored(self):
        ci = ConfidenceInputs(
            objective_clarity=90.0,
            scope_clarity=85.0,
            evidence_quality=70.0,
            reversibility=60.0,
            tool_fit=75.0,
            risk_awareness=80.0,
            testability=65.0,
        )
        assert ci.objective_clarity == 90.0
        assert ci.scope_clarity == 85.0
        assert ci.evidence_quality == 70.0
        assert ci.reversibility == 60.0
        assert ci.tool_fit == 75.0
        assert ci.risk_awareness == 80.0
        assert ci.testability == 65.0

    def test_accepts_float_zero(self):
        ci = _zero()
        assert ci.objective_clarity == 0.0

    def test_accepts_float_hundred(self):
        ci = _perfect()
        assert ci.testability == 100.0


# ---------------------------------------------------------------------------
# score_confidence — weight arithmetic
# ---------------------------------------------------------------------------


class TestScoreConfidence:
    def test_perfect_inputs_return_100(self):
        assert score_confidence(_perfect()) == 100.0

    def test_zero_inputs_return_0(self):
        assert score_confidence(_zero()) == 0.0

    def test_uniform_80_returns_80(self):
        result = score_confidence(_inputs())
        assert result == 80.0

    def test_result_is_float(self):
        result = score_confidence(_inputs())
        assert isinstance(result, float)

    def test_result_is_rounded_to_2dp(self):
        ci = ConfidenceInputs(
            objective_clarity=33.3,
            scope_clarity=33.3,
            evidence_quality=33.3,
            reversibility=33.3,
            tool_fit=33.3,
            risk_awareness=33.3,
            testability=33.3,
        )
        result = score_confidence(ci)
        assert result == round(result, 2)

    def test_weights_sum_to_one(self):
        """Isolated dimension tests: each weight at 100, rest 0 → sum to 100."""
        dims = [
            "objective_clarity",
            "scope_clarity",
            "evidence_quality",
            "reversibility",
            "tool_fit",
            "risk_awareness",
            "testability",
        ]
        total = 0.0
        for dim in dims:
            kwargs = {d: 0.0 for d in dims}
            kwargs[dim] = 100.0
            total += score_confidence(_inputs(**kwargs))
        assert abs(total - 100.0) < 0.01

    def test_objective_clarity_contributes_20(self):
        ci = _inputs(
            objective_clarity=100.0,
            scope_clarity=0.0,
            evidence_quality=0.0,
            reversibility=0.0,
            tool_fit=0.0,
            risk_awareness=0.0,
            testability=0.0,
        )
        assert score_confidence(ci) == 20.0

    def test_scope_clarity_contributes_20(self):
        ci = _inputs(
            objective_clarity=0.0,
            scope_clarity=100.0,
            evidence_quality=0.0,
            reversibility=0.0,
            tool_fit=0.0,
            risk_awareness=0.0,
            testability=0.0,
        )
        assert score_confidence(ci) == 20.0

    def test_evidence_quality_contributes_20(self):
        ci = _inputs(
            objective_clarity=0.0,
            scope_clarity=0.0,
            evidence_quality=100.0,
            reversibility=0.0,
            tool_fit=0.0,
            risk_awareness=0.0,
            testability=0.0,
        )
        assert score_confidence(ci) == 20.0

    def test_reversibility_contributes_10(self):
        ci = _inputs(
            objective_clarity=0.0,
            scope_clarity=0.0,
            evidence_quality=0.0,
            reversibility=100.0,
            tool_fit=0.0,
            risk_awareness=0.0,
            testability=0.0,
        )
        assert score_confidence(ci) == 10.0

    def test_testability_contributes_10(self):
        ci = _inputs(
            objective_clarity=0.0,
            scope_clarity=0.0,
            evidence_quality=0.0,
            reversibility=0.0,
            tool_fit=0.0,
            risk_awareness=0.0,
            testability=100.0,
        )
        assert score_confidence(ci) == 10.0

    def test_partial_scores_accumulate(self):
        # objective_clarity=100 → 20; scope_clarity=50 → 10; rest=0 → total 30
        ci = _inputs(
            objective_clarity=100.0,
            scope_clarity=50.0,
            evidence_quality=0.0,
            reversibility=0.0,
            tool_fit=0.0,
            risk_awareness=0.0,
            testability=0.0,
        )
        assert score_confidence(ci) == 30.0

    def test_monotone_increase_with_inputs(self):
        low = score_confidence(_inputs(objective_clarity=20.0))
        high = score_confidence(_inputs(objective_clarity=90.0))
        assert high > low

    def test_mixed_inputs_in_range(self):
        ci = ConfidenceInputs(
            objective_clarity=70.0,
            scope_clarity=60.0,
            evidence_quality=80.0,
            reversibility=50.0,
            tool_fit=90.0,
            risk_awareness=40.0,
            testability=55.0,
        )
        result = score_confidence(ci)
        assert 0.0 <= result <= 100.0


# ---------------------------------------------------------------------------
# decision_from_score — threshold bands
# ---------------------------------------------------------------------------


class TestDecisionFromScore:
    def test_90_and_above_proceed(self):
        assert decision_from_score(90.0) == "proceed"
        assert decision_from_score(100.0) == "proceed"
        assert decision_from_score(95.5) == "proceed"

    def test_75_to_89_proceed_reversible_only(self):
        assert decision_from_score(75.0) == "proceed_reversible_only"
        assert decision_from_score(89.9) == "proceed_reversible_only"
        assert decision_from_score(80.0) == "proceed_reversible_only"

    def test_50_to_74_replan(self):
        assert decision_from_score(50.0) == "replan"
        assert decision_from_score(74.9) == "replan"
        assert decision_from_score(60.0) == "replan"

    def test_below_50_halt(self):
        assert decision_from_score(49.9) == "halt"
        assert decision_from_score(0.0) == "halt"
        assert decision_from_score(10.0) == "halt"

    def test_human_gate_required_overrides_any_score(self):
        assert decision_from_score(100.0, human_gate_required=True) == "review"
        assert decision_from_score(90.0, human_gate_required=True) == "review"
        assert decision_from_score(50.0, human_gate_required=True) == "review"
        assert decision_from_score(0.0, human_gate_required=True) == "review"

    def test_human_gate_false_uses_normal_bands(self):
        assert decision_from_score(95.0, human_gate_required=False) == "proceed"

    def test_exact_boundary_90(self):
        assert decision_from_score(90.0) == "proceed"

    def test_exact_boundary_75(self):
        assert decision_from_score(75.0) == "proceed_reversible_only"

    def test_exact_boundary_50(self):
        assert decision_from_score(50.0) == "replan"

    def test_just_below_90(self):
        assert decision_from_score(89.99) == "proceed_reversible_only"

    def test_just_below_75(self):
        assert decision_from_score(74.99) == "replan"

    def test_just_below_50(self):
        assert decision_from_score(49.99) == "halt"

    def test_return_type_is_str(self):
        assert isinstance(decision_from_score(80.0), str)


# ---------------------------------------------------------------------------
# score_confidence + decision_from_score integration
# ---------------------------------------------------------------------------


class TestScoringDecisionIntegration:
    def test_perfect_inputs_lead_to_proceed(self):
        score = score_confidence(_perfect())
        decision = decision_from_score(score)
        assert decision == "proceed"

    def test_zero_inputs_lead_to_halt(self):
        score = score_confidence(_zero())
        decision = decision_from_score(score)
        assert decision == "halt"

    def test_high_clarity_leads_to_proceed(self):
        ci = ConfidenceInputs(
            objective_clarity=100.0,
            scope_clarity=100.0,
            evidence_quality=100.0,
            reversibility=80.0,
            tool_fit=80.0,
            risk_awareness=80.0,
            testability=80.0,
        )
        score = score_confidence(ci)
        decision = decision_from_score(score)
        assert decision == "proceed"

    def test_moderate_clarity_replan(self):
        ci = ConfidenceInputs(
            objective_clarity=50.0,
            scope_clarity=50.0,
            evidence_quality=50.0,
            reversibility=50.0,
            tool_fit=50.0,
            risk_awareness=50.0,
            testability=50.0,
        )
        score = score_confidence(ci)
        decision = decision_from_score(score)
        assert decision == "replan"

    def test_human_gate_overrides_perfect_score(self):
        score = score_confidence(_perfect())
        decision = decision_from_score(score, human_gate_required=True)
        assert decision == "review"

    def test_confidence_decay_simulation(self):
        """Simulate confidence degradation: each retry drops a signal by 10."""
        base = _inputs(
            objective_clarity=90.0,
            scope_clarity=90.0,
            evidence_quality=90.0,
        )
        scores = []
        for retry in range(4):
            degraded = _inputs(
                objective_clarity=max(0.0, 90.0 - retry * 15),
                scope_clarity=max(0.0, 90.0 - retry * 15),
                evidence_quality=max(0.0, 90.0 - retry * 15),
                reversibility=base.reversibility,
                tool_fit=base.tool_fit,
                risk_awareness=base.risk_awareness,
                testability=base.testability,
            )
            scores.append(score_confidence(degraded))
        # Scores should be monotonically decreasing
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_aggregate_from_multiple_signals(self):
        """High scores on weighted dimensions dominate aggregate."""
        # objective_clarity + scope_clarity + evidence_quality = 60% weight
        dominant = _inputs(
            objective_clarity=100.0,
            scope_clarity=100.0,
            evidence_quality=100.0,
            reversibility=0.0,
            tool_fit=0.0,
            risk_awareness=0.0,
            testability=0.0,
        )
        score = score_confidence(dominant)
        # 0.20*100 + 0.20*100 + 0.20*100 = 60
        assert score == 60.0
