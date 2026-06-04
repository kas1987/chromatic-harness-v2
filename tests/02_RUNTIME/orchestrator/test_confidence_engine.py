"""Tests for orchestrator/confidence_engine.py.

# DEFICIENCIES NOTED
# --------------------------------------------------------------------------
# 1. score_confidence accepts values outside [0, 100] — negative inputs and
#    values above 100 produce scores outside the expected [0, 100] range with
#    no validation, guard, or documented contract. The function is purely
#    arithmetic and does not clamp or raise.
# 2. score_confidence accepts non-numeric types that Python will attempt to
#    multiply; only TypeError surfaces at arithmetic time, not at construction
#    of ConfidenceInputs (dataclass has no __post_init__ validation).
# 3. decision_from_score has no guard against scores outside [0, 100] (e.g.
#    score=-5 falls to "halt", score=150 → "proceed" — both silently work but
#    may be semantically wrong).
# 4. The module has no module-level __all__ or public API declaration.
# 5. No async surface; module is synchronous-only — no async concerns to test.
# --------------------------------------------------------------------------
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

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

    def test_is_dataclass(self):
        """ConfidenceInputs is a dataclass — it must support equality."""
        a = _inputs(objective_clarity=50.0)
        b = _inputs(objective_clarity=50.0)
        assert a == b

    def test_inequality_on_differing_field(self):
        a = _inputs(objective_clarity=50.0)
        b = _inputs(objective_clarity=51.0)
        assert a != b

    def test_all_seven_fields_exist(self):
        ci = _perfect()
        for field in (
            "objective_clarity",
            "scope_clarity",
            "evidence_quality",
            "reversibility",
            "tool_fit",
            "risk_awareness",
            "testability",
        ):
            assert hasattr(ci, field), f"Missing field: {field}"

    @pytest.mark.parametrize(
        "field,value",
        [
            ("objective_clarity", 0.0),
            ("objective_clarity", 50.0),
            ("objective_clarity", 100.0),
            ("scope_clarity", 25.5),
            ("evidence_quality", 99.99),
            ("reversibility", 1.0),
            ("tool_fit", 77.77),
            ("risk_awareness", 33.33),
            ("testability", 66.6),
        ],
    )
    def test_individual_field_stores_value(self, field, value):
        ci = _inputs(**{field: value})
        assert getattr(ci, field) == value


# ---------------------------------------------------------------------------
# score_confidence — weight arithmetic (parametrized)
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

    def test_tool_fit_contributes_10(self):
        ci = _inputs(
            objective_clarity=0.0,
            scope_clarity=0.0,
            evidence_quality=0.0,
            reversibility=0.0,
            tool_fit=100.0,
            risk_awareness=0.0,
            testability=0.0,
        )
        assert score_confidence(ci) == 10.0

    def test_risk_awareness_contributes_10(self):
        ci = _inputs(
            objective_clarity=0.0,
            scope_clarity=0.0,
            evidence_quality=0.0,
            reversibility=0.0,
            tool_fit=0.0,
            risk_awareness=100.0,
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

    # ------------------------------------------------------------------
    # Parametrized arithmetic table — concrete input→output pairs
    # Weight formula:
    #   0.20*oc + 0.20*sc + 0.20*eq + 0.10*rev + 0.10*tf + 0.10*ra + 0.10*tb
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "oc,sc,eq,rev,tf,ra,tb,expected",
        [
            # All uniform values
            (100, 100, 100, 100, 100, 100, 100, 100.0),
            (0, 0, 0, 0, 0, 0, 0, 0.0),
            (50, 50, 50, 50, 50, 50, 50, 50.0),
            (80, 80, 80, 80, 80, 80, 80, 80.0),
            (10, 10, 10, 10, 10, 10, 10, 10.0),
            # Only the three 20%-weight fields at 100
            (100, 100, 100, 0, 0, 0, 0, 60.0),
            # Only the four 10%-weight fields at 100
            (0, 0, 0, 100, 100, 100, 100, 40.0),
            # One 20%-weight field at 100, all others 0
            (100, 0, 0, 0, 0, 0, 0, 20.0),
            (0, 100, 0, 0, 0, 0, 0, 20.0),
            (0, 0, 100, 0, 0, 0, 0, 20.0),
            # One 10%-weight field at 100, all others 0
            (0, 0, 0, 100, 0, 0, 0, 10.0),
            (0, 0, 0, 0, 100, 0, 0, 10.0),
            (0, 0, 0, 0, 0, 100, 0, 10.0),
            (0, 0, 0, 0, 0, 0, 100, 10.0),
            # Mixed realistic scores
            # 0.20*90 + 0.20*85 + 0.20*80 + 0.10*70 + 0.10*75 + 0.10*60 + 0.10*65
            # = 18 + 17 + 16 + 7 + 7.5 + 6 + 6.5 = 78
            (90, 85, 80, 70, 75, 60, 65, 78.0),
            # 0.20*100 + 0.20*100 + 0.20*100 + 0.10*50 + 0.10*50 + 0.10*50 + 0.10*50
            # = 20 + 20 + 20 + 5 + 5 + 5 + 5 = 80
            (100, 100, 100, 50, 50, 50, 50, 80.0),
            # Low clarity, high secondary
            # 0.20*10 + 0.20*10 + 0.20*10 + 0.10*100 + 0.10*100 + 0.10*100 + 0.10*100
            # = 2 + 2 + 2 + 10 + 10 + 10 + 10 = 46
            (10, 10, 10, 100, 100, 100, 100, 46.0),
            # Exact 75 boundary
            # need sum = 75: 0.20*oc + 0.20*sc + 0.20*eq + 0.10*(rev+tf+ra+tb) = 75
            # use all = 75: 0.60*75 + 0.40*75 = 45 + 30 = 75
            (75, 75, 75, 75, 75, 75, 75, 75.0),
            # Exact 90 boundary
            (90, 90, 90, 90, 90, 90, 90, 90.0),
            # Exact 50 boundary
            (50, 50, 50, 50, 50, 50, 50, 50.0),
            # 25 percent across board
            (25, 25, 25, 25, 25, 25, 25, 25.0),
        ],
    )
    def test_score_arithmetic(self, oc, sc, eq, rev, tf, ra, tb, expected):
        ci = ConfidenceInputs(
            objective_clarity=float(oc),
            scope_clarity=float(sc),
            evidence_quality=float(eq),
            reversibility=float(rev),
            tool_fit=float(tf),
            risk_awareness=float(ra),
            testability=float(tb),
        )
        assert score_confidence(ci) == expected

    @pytest.mark.parametrize(
        "oc,sc,eq,rev,tf,ra,tb,expected",
        [
            # 0.20*33.3 + 0.20*33.3 + 0.20*33.3 + 0.10*33.3*4
            # = 6.66 + 6.66 + 6.66 + 13.32 = 33.3
            (33.3, 33.3, 33.3, 33.3, 33.3, 33.3, 33.3, 33.3),
            # 0.20*66.7 * 3 + 0.10*66.7 * 4 = 40.02 + 26.68 = 66.7
            (66.7, 66.7, 66.7, 66.7, 66.7, 66.7, 66.7, 66.7),
            # 0.20*1.5*3 + 0.10*1.5*4 = 0.9 + 0.6 = 1.5
            (1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5),
        ],
    )
    def test_score_fractional_inputs(self, oc, sc, eq, rev, tf, ra, tb, expected):
        ci = ConfidenceInputs(
            objective_clarity=float(oc),
            scope_clarity=float(sc),
            evidence_quality=float(eq),
            reversibility=float(rev),
            tool_fit=float(tf),
            risk_awareness=float(ra),
            testability=float(tb),
        )
        assert abs(score_confidence(ci) - expected) < 0.01

    def test_idempotent_same_inputs_same_output(self):
        ci = _inputs(objective_clarity=77.7, scope_clarity=55.5)
        r1 = score_confidence(ci)
        r2 = score_confidence(ci)
        assert r1 == r2

    def test_result_rounded_not_raw_float(self):
        """Inputs that would give many decimal places must be rounded to 2 dp."""
        ci = ConfidenceInputs(
            objective_clarity=1.0,
            scope_clarity=1.0,
            evidence_quality=1.0,
            reversibility=1.0,
            tool_fit=1.0,
            risk_awareness=1.0,
            testability=1.0,
        )
        result = score_confidence(ci)
        # 0.20*1 * 3 + 0.10*1 * 4 = 0.6 + 0.4 = 1.0 — still check 2dp invariant
        assert result == round(result, 2)

    # ------------------------------------------------------------------
    # Boundary conditions
    # ------------------------------------------------------------------

    def test_single_unit_objective_clarity(self):
        # 0.20 * 1.0 = 0.2
        ci = _inputs(
            objective_clarity=1.0,
            scope_clarity=0.0,
            evidence_quality=0.0,
            reversibility=0.0,
            tool_fit=0.0,
            risk_awareness=0.0,
            testability=0.0,
        )
        assert score_confidence(ci) == 0.2

    def test_single_unit_reversibility(self):
        # 0.10 * 1.0 = 0.1
        ci = _inputs(
            objective_clarity=0.0,
            scope_clarity=0.0,
            evidence_quality=0.0,
            reversibility=1.0,
            tool_fit=0.0,
            risk_awareness=0.0,
            testability=0.0,
        )
        assert score_confidence(ci) == 0.1

    def test_near_zero_inputs_still_positive(self):
        ci = _inputs(
            objective_clarity=0.01,
            scope_clarity=0.01,
            evidence_quality=0.01,
            reversibility=0.01,
            tool_fit=0.01,
            risk_awareness=0.01,
            testability=0.01,
        )
        result = score_confidence(ci)
        assert result > 0.0

    def test_near_100_inputs_still_not_exceeding_100(self):
        ci = _inputs(
            objective_clarity=99.99,
            scope_clarity=99.99,
            evidence_quality=99.99,
            reversibility=99.99,
            tool_fit=99.99,
            risk_awareness=99.99,
            testability=99.99,
        )
        result = score_confidence(ci)
        assert result <= 100.0

    # ------------------------------------------------------------------
    # Out-of-range inputs (deficiency: no validation — document behavior)
    # ------------------------------------------------------------------

    def test_negative_inputs_produce_negative_score(self):
        """Deficiency: no clamping — negative inputs flow through to negative score."""
        ci = ConfidenceInputs(
            objective_clarity=-100.0,
            scope_clarity=-100.0,
            evidence_quality=-100.0,
            reversibility=-100.0,
            tool_fit=-100.0,
            risk_awareness=-100.0,
            testability=-100.0,
        )
        result = score_confidence(ci)
        assert result < 0.0

    def test_over_100_inputs_produce_over_100_score(self):
        """Deficiency: no clamping — inputs > 100 yield score > 100."""
        ci = ConfidenceInputs(
            objective_clarity=200.0,
            scope_clarity=200.0,
            evidence_quality=200.0,
            reversibility=200.0,
            tool_fit=200.0,
            risk_awareness=200.0,
            testability=200.0,
        )
        result = score_confidence(ci)
        assert result > 100.0

    def test_single_negative_dimension_lowers_score(self):
        """One negative dimension reduces the aggregate score."""
        normal = score_confidence(_inputs())
        with_negative = score_confidence(_inputs(objective_clarity=-50.0))
        assert with_negative < normal

    def test_single_over_range_dimension_raises_score(self):
        """One over-range dimension inflates the aggregate score."""
        normal = score_confidence(_inputs())
        inflated = score_confidence(_inputs(objective_clarity=200.0))
        assert inflated > normal

    def test_non_numeric_type_raises_type_error(self):
        """Deficiency: dataclass accepts non-numeric — fails at arithmetic time."""
        ci = ConfidenceInputs(
            objective_clarity="high",  # type: ignore[arg-type]
            scope_clarity=80.0,
            evidence_quality=80.0,
            reversibility=80.0,
            tool_fit=80.0,
            risk_awareness=80.0,
            testability=80.0,
        )
        with pytest.raises(TypeError):
            score_confidence(ci)

    def test_none_type_raises(self):
        """Deficiency: no validation — None causes TypeError at arithmetic."""
        ci = ConfidenceInputs(
            objective_clarity=None,  # type: ignore[arg-type]
            scope_clarity=80.0,
            evidence_quality=80.0,
            reversibility=80.0,
            tool_fit=80.0,
            risk_awareness=80.0,
            testability=80.0,
        )
        with pytest.raises(TypeError):
            score_confidence(ci)

    # ------------------------------------------------------------------
    # Weight precision: each dimension's weight is exact
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "dimension,weight",
        [
            ("objective_clarity", 0.20),
            ("scope_clarity", 0.20),
            ("evidence_quality", 0.20),
            ("reversibility", 0.10),
            ("tool_fit", 0.10),
            ("risk_awareness", 0.10),
            ("testability", 0.10),
        ],
    )
    def test_dimension_weight(self, dimension, weight):
        """Each dimension set to 1.0 contributes exactly its weight."""
        dims = [
            "objective_clarity",
            "scope_clarity",
            "evidence_quality",
            "reversibility",
            "tool_fit",
            "risk_awareness",
            "testability",
        ]
        kwargs = {d: 0.0 for d in dims}
        kwargs[dimension] = 1.0
        result = score_confidence(ConfidenceInputs(**kwargs))
        assert abs(result - weight) < 1e-9

    @pytest.mark.parametrize(
        "dimension,weight",
        [
            ("objective_clarity", 0.20),
            ("scope_clarity", 0.20),
            ("evidence_quality", 0.20),
            ("reversibility", 0.10),
            ("tool_fit", 0.10),
            ("risk_awareness", 0.10),
            ("testability", 0.10),
        ],
    )
    def test_dimension_linear_scaling(self, dimension, weight):
        """Score increases linearly with each dimension."""
        dims = [
            "objective_clarity",
            "scope_clarity",
            "evidence_quality",
            "reversibility",
            "tool_fit",
            "risk_awareness",
            "testability",
        ]
        for raw_value in (0, 25, 50, 75, 100):
            kwargs = {d: 0.0 for d in dims}
            kwargs[dimension] = float(raw_value)
            expected = round(raw_value * weight, 2)
            result = score_confidence(ConfidenceInputs(**kwargs))
            assert abs(result - expected) < 0.01, f"{dimension}={raw_value}: expected {expected}, got {result}"


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

    # ------------------------------------------------------------------
    # Parametrized decision bands
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "score,expected",
        [
            # "proceed" band: score >= 90
            (90.0, "proceed"),
            (90.01, "proceed"),
            (95.0, "proceed"),
            (99.0, "proceed"),
            (100.0, "proceed"),
            # "proceed_reversible_only" band: 75 <= score < 90
            (75.0, "proceed_reversible_only"),
            (75.01, "proceed_reversible_only"),
            (80.0, "proceed_reversible_only"),
            (85.0, "proceed_reversible_only"),
            (89.0, "proceed_reversible_only"),
            (89.99, "proceed_reversible_only"),
            # "replan" band: 50 <= score < 75
            (50.0, "replan"),
            (50.01, "replan"),
            (60.0, "replan"),
            (70.0, "replan"),
            (74.0, "replan"),
            (74.99, "replan"),
            # "halt" band: score < 50
            (49.99, "halt"),
            (49.0, "halt"),
            (25.0, "halt"),
            (10.0, "halt"),
            (1.0, "halt"),
            (0.0, "halt"),
            (0.01, "halt"),
        ],
    )
    def test_decision_bands_parametrized(self, score, expected):
        assert decision_from_score(score) == expected

    @pytest.mark.parametrize(
        "score",
        [0.0, 10.0, 25.0, 49.99, 50.0, 60.0, 74.99, 75.0, 85.0, 89.99, 90.0, 100.0],
    )
    def test_human_gate_always_review(self, score):
        assert decision_from_score(score, human_gate_required=True) == "review"

    @pytest.mark.parametrize(
        "score,expected",
        [
            # Deficiency: out-of-range scores resolve without error
            (-1.0, "halt"),
            (-100.0, "halt"),
            (101.0, "proceed"),
            (200.0, "proceed"),
        ],
    )
    def test_out_of_range_scores_resolve_silently(self, score, expected):
        """Deficiency: no guard on out-of-range — documents current behavior."""
        assert decision_from_score(score) == expected

    def test_human_gate_default_is_false(self):
        """human_gate_required defaults to False — confirm normal path fires."""
        assert decision_from_score(95.0) == "proceed"

    def test_all_four_decisions_are_valid_strings(self):
        expected_decisions = {"proceed", "proceed_reversible_only", "replan", "halt", "review"}
        for score in (100, 80, 60, 25):
            assert decision_from_score(float(score)) in expected_decisions
        assert decision_from_score(80.0, human_gate_required=True) in expected_decisions

    @pytest.mark.parametrize(
        "score",
        [90.0, 75.0, 50.0],
    )
    def test_boundary_idempotent(self, score):
        """Calling decision_from_score twice with the same score gives same result."""
        assert decision_from_score(score) == decision_from_score(score)


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
        """Simulate confidence degradation: each retry drops a signal by 15."""
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

    # ------------------------------------------------------------------
    # Parametrized end-to-end: inputs → score → decision
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "oc,sc,eq,rev,tf,ra,tb,expected_decision",
        [
            # Perfect → proceed
            (100, 100, 100, 100, 100, 100, 100, "proceed"),
            # All 90 → score=90 → proceed
            (90, 90, 90, 90, 90, 90, 90, "proceed"),
            # All 80 → score=80 → proceed_reversible_only
            (80, 80, 80, 80, 80, 80, 80, "proceed_reversible_only"),
            # All 75 → score=75 → proceed_reversible_only
            (75, 75, 75, 75, 75, 75, 75, "proceed_reversible_only"),
            # All 60 → score=60 → replan
            (60, 60, 60, 60, 60, 60, 60, "replan"),
            # All 50 → score=50 → replan
            (50, 50, 50, 50, 50, 50, 50, "replan"),
            # All 25 → score=25 → halt
            (25, 25, 25, 25, 25, 25, 25, "halt"),
            # All 0 → score=0 → halt
            (0, 0, 0, 0, 0, 0, 0, "halt"),
            # High clarity dims (60% weight) at 100, rest at 0 → score=60 → replan
            (100, 100, 100, 0, 0, 0, 0, "replan"),
            # Low clarity, high secondary → score ~= 46 → halt (< 50)
            (10, 10, 10, 100, 100, 100, 100, "halt"),
            # 0.20*90 + 0.20*85 + 0.20*80 + 0.10*70 + 0.10*75 + 0.10*60 + 0.10*65
            # = 18+17+16+7+7.5+6+6.5 = 78 → proceed_reversible_only
            (90, 85, 80, 70, 75, 60, 65, "proceed_reversible_only"),
            # 0.20*95 + 0.20*95 + 0.20*95 + 0.10*80 + 0.10*80 + 0.10*80 + 0.10*80
            # = 19+19+19+8+8+8+8 = 89 → proceed_reversible_only (< 90)
            (95, 95, 95, 80, 80, 80, 80, "proceed_reversible_only"),
            # 0.20*100 + 0.20*100 + 0.20*100 + 0.10*80 + 0.10*80 + 0.10*80 + 0.10*80
            # = 20+20+20+8+8+8+8 = 92 → proceed
            (100, 100, 100, 80, 80, 80, 80, "proceed"),
        ],
    )
    def test_full_pipeline_parametrized(self, oc, sc, eq, rev, tf, ra, tb, expected_decision):
        ci = ConfidenceInputs(
            objective_clarity=float(oc),
            scope_clarity=float(sc),
            evidence_quality=float(eq),
            reversibility=float(rev),
            tool_fit=float(tf),
            risk_awareness=float(ra),
            testability=float(tb),
        )
        score = score_confidence(ci)
        decision = decision_from_score(score)
        assert decision == expected_decision

    @pytest.mark.parametrize(
        "oc,sc,eq,rev,tf,ra,tb,expected_score",
        [
            # Verify the score for inputs that sit right at decision boundaries
            # Score exactly 90.0 — proceed
            (90, 90, 90, 90, 90, 90, 90, 90.0),
            # Score exactly 75.0 — proceed_reversible_only
            (75, 75, 75, 75, 75, 75, 75, 75.0),
            # Score exactly 50.0 — replan
            (50, 50, 50, 50, 50, 50, 50, 50.0),
        ],
    )
    def test_boundary_score_values(self, oc, sc, eq, rev, tf, ra, tb, expected_score):
        ci = ConfidenceInputs(
            objective_clarity=float(oc),
            scope_clarity=float(sc),
            evidence_quality=float(eq),
            reversibility=float(rev),
            tool_fit=float(tf),
            risk_awareness=float(ra),
            testability=float(tb),
        )
        assert score_confidence(ci) == expected_score

    def test_human_gate_review_pipeline_all_inputs(self):
        """human_gate_required=True always returns review regardless of inputs."""
        for score_value in (0, 25, 50, 75, 80, 90, 100):
            ci = ConfidenceInputs(
                objective_clarity=float(score_value),
                scope_clarity=float(score_value),
                evidence_quality=float(score_value),
                reversibility=float(score_value),
                tool_fit=float(score_value),
                risk_awareness=float(score_value),
                testability=float(score_value),
            )
            score = score_confidence(ci)
            assert decision_from_score(score, human_gate_required=True) == "review"

    def test_near_boundary_90_score_91(self):
        """Score of 91 should be 'proceed', not at a boundary ambiguity."""
        ci = ConfidenceInputs(
            objective_clarity=91.0,
            scope_clarity=91.0,
            evidence_quality=91.0,
            reversibility=91.0,
            tool_fit=91.0,
            risk_awareness=91.0,
            testability=91.0,
        )
        score = score_confidence(ci)
        assert score == 91.0
        assert decision_from_score(score) == "proceed"

    def test_near_boundary_89_score_proceeds_reversible_only(self):
        ci = ConfidenceInputs(
            objective_clarity=89.0,
            scope_clarity=89.0,
            evidence_quality=89.0,
            reversibility=89.0,
            tool_fit=89.0,
            risk_awareness=89.0,
            testability=89.0,
        )
        score = score_confidence(ci)
        assert score == 89.0
        assert decision_from_score(score) == "proceed_reversible_only"

    def test_score_monotonicity_across_uniform_inputs(self):
        """As uniform input increases from 0→100, score increases monotonically."""
        prev_score = -1.0
        for v in range(0, 101, 5):
            ci = ConfidenceInputs(
                objective_clarity=float(v),
                scope_clarity=float(v),
                evidence_quality=float(v),
                reversibility=float(v),
                tool_fit=float(v),
                risk_awareness=float(v),
                testability=float(v),
            )
            score = score_confidence(ci)
            assert score >= prev_score
            prev_score = score

    def test_decision_ordering_consistency_with_scores(self):
        """Higher scores must never produce a less permissive decision."""
        band_order = {
            "halt": 0,
            "replan": 1,
            "proceed_reversible_only": 2,
            "proceed": 3,
            "review": 4,  # review is bypass, skip in comparison
        }
        score_pairs = [
            (0.0, 50.0),
            (49.0, 75.0),
            (74.0, 90.0),
            (89.0, 100.0),
        ]
        for low_score, high_score in score_pairs:
            d_low = decision_from_score(low_score)
            d_high = decision_from_score(high_score)
            assert band_order[d_low] <= band_order[d_high], (
                f"score {high_score} → '{d_high}' is less permissive than score {low_score} → '{d_low}'"
            )
