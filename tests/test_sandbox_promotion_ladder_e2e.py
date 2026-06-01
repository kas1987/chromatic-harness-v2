"""E2E tests for Sandbox Lab promotion ladder (L0-L5) via the real TypeScript PromotionScorer.

Uses a subprocess bridge to call `02_RUNTIME/sandbox-lab/promotion-scorer-cli.ts` via
`npx tsx` so tests exercise the actual production logic rather than a Python shadow copy.
This prevents silent drift when TypeScript gate thresholds change.
"""

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace


_CLI_PATH = Path(__file__).resolve().parents[1] / "02_RUNTIME" / "sandbox-lab" / "promotion-scorer-cli.ts"

# On Windows, subprocess.run needs the .cmd extension; shutil.which finds it.
_NPX = shutil.which("npx") or "npx"


def _score(
    agent_id: str,
    current_level: int,
    successful_executions: int,
    success_rate: float,
    avg_confidence: float,
    last_execution_errors: int,
    scope_violations: int,
    risk_score: float = 0.1,
) -> SimpleNamespace:
    """Call the real TypeScript PromotionScorer.scorePromotion() and return the decision."""
    payload = {
        "agent_id": agent_id,
        "current_level": current_level,
        "successful_executions": successful_executions,
        "success_rate": success_rate,
        "avg_confidence": avg_confidence,
        "last_execution_errors": last_execution_errors,
        "scope_violations": scope_violations,
        "risk_score": risk_score,
    }
    result = subprocess.run(
        f'npx tsx "{_CLI_PATH}"',
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        shell=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"TS PromotionScorer CLI failed (exit {result.returncode}):\n{result.stderr}")
    data = json.loads(result.stdout.strip())
    return SimpleNamespace(**data)


class TestSandboxPromotionLadderE2E:
    """E2E tests for sandbox promotion ladder via real TypeScript PromotionScorer.

    Gate thresholds come from DEFAULT_SANDBOX_CONFIG in sandbox-types.ts:
      - min_executions_per_level: 3 (all levels)
      - confidence_threshold_per_level: {1:0.6, 2:0.7, 3:0.75, 4:0.85, 5:0.9}
      - error_threshold: 2  (errors > 2 blocks promotion)
      - scope_violation_threshold: 1  (violations > 1 blocks promotion)
      - success_rate < 0.8 blocks promotion
    """

    def test_l0_to_l1_basic_reasoning_gate(self):
        """L0 -> L1 requires 3+ execs, 80%+ success, conf >= 0.6, errors <= 2, violations <= 1."""
        d = _score("agent-test-1", 0, 3, 0.85, 0.65, 0, 0)
        assert d.ready_to_promote is True
        assert d.recommended_level == 1

    def test_l0_to_l1_insufficient_executions_blocked(self):
        """L0 -> L1 blocked if fewer than 3 successful executions."""
        d = _score("agent-test-2", 0, 2, 0.90, 0.80, 0, 0)
        assert d.ready_to_promote is False
        assert d.recommended_level == "stay"
        assert any("2 successful executions" in issue for issue in d.issues)

    def test_l1_to_l2_scope_validation_gate(self):
        """L1 -> L2 passes with 0 violations and confidence >= 0.7."""
        d = _score("agent-test-3", 1, 5, 0.90, 0.75, 0, 0)
        assert d.ready_to_promote is True
        assert d.recommended_level == 2

    def test_l1_to_l2_scope_violation_blocks_promotion(self):
        """L1 -> L2 blocked when scope violations exceed threshold (>1 in TS config)."""
        # TS scope_violation_threshold=1; need violations=2 to block (not 1 like Python shadow used)
        d = _score("agent-test-4", 1, 5, 0.95, 0.80, 0, 2)
        assert d.ready_to_promote is False
        assert any("violation" in issue.lower() for issue in d.issues)

    def test_l2_to_l3_patch_quality_gate(self):
        """L2 -> L3 requires confidence >= 0.75."""
        d = _score("agent-test-5", 2, 8, 0.92, 0.80, 0, 0)
        assert d.ready_to_promote is True
        assert d.recommended_level == 3

    def test_l2_to_l3_recent_errors_block(self):
        """L2 -> L3 blocked when last execution errors exceed threshold (>2 in TS config)."""
        # TS error_threshold=2; need errors=3 to block (not 1 like Python shadow used)
        d = _score("agent-test-6", 2, 8, 0.92, 0.80, 3, 0)
        assert d.ready_to_promote is False
        assert any("error" in issue.lower() for issue in d.issues)

    def test_l3_to_l4_container_reliability_gate(self):
        """L3 -> L4 requires confidence >= 0.85."""
        d = _score("agent-test-7", 3, 10, 0.96, 0.87, 0, 0)
        assert d.ready_to_promote is True
        assert d.recommended_level == 4

    def test_l3_to_l4_confidence_insufficient(self):
        """L3 -> L4 blocked if confidence below 0.85."""
        d = _score("agent-test-8", 3, 10, 0.96, 0.80, 0, 0)
        assert d.ready_to_promote is False
        assert any("confidence" in issue.lower() for issue in d.issues)

    def test_l4_to_l5_merge_capability_gate(self):
        """L4 -> L5 requires confidence >= 0.9."""
        d = _score("agent-test-9", 4, 15, 0.98, 0.92, 0, 0)
        assert d.ready_to_promote is True
        assert d.recommended_level == 5

    def test_l4_to_l5_low_success_rate_blocks(self):
        """L4 -> L5 blocked when success rate below 80% threshold."""
        # TS uses a flat 80% success rate for all levels; < 80% blocks
        d = _score("agent-test-10", 4, 15, 0.70, 0.92, 0, 0)
        assert d.ready_to_promote is False
        assert any("success rate" in issue.lower() for issue in d.issues)

    def test_l5_no_further_promotion(self):
        """L5 agent stays at max level; no further promotion."""
        d = _score("agent-test-11", 5, 100, 1.0, 1.0, 0, 0)
        assert d.ready_to_promote is False
        assert d.recommended_level == "stay"
        assert d.current_level == 5
        assert "maximum trust level" in d.reason.lower() or "l5" in d.reason.lower()

    def test_complete_progression_path_l0_to_l5(self):
        """Full progression from L0 to L5 with all gates passed."""
        agent_id = "agent-climber"
        progression = []

        for level, execs, success, conf in [
            (0, 3, 0.85, 0.65),  # L0->L1: conf >= 0.6
            (1, 5, 0.90, 0.75),  # L1->L2: conf >= 0.7
            (2, 8, 0.92, 0.80),  # L2->L3: conf >= 0.75
            (3, 10, 0.96, 0.87),  # L3->L4: conf >= 0.85
            (4, 15, 0.98, 0.92),  # L4->L5: conf >= 0.9
        ]:
            d = _score(agent_id, level, execs, success, conf, 0, 0)
            assert d.ready_to_promote is True, f"L{level}->L{level + 1} should pass"
            progression.append((f"L{level}->L{level + 1}", d))

        d_max = _score(agent_id, 5, 100, 1.0, 1.0, 0, 0)
        assert d_max.ready_to_promote is False
        assert d_max.recommended_level == "stay"
        progression.append(("L5 (max)", d_max))

        assert len(progression) == 6

    def test_demotion_scenario_high_error_rate(self):
        """Multiple critical failures produce very low confidence score."""
        d = _score(
            "agent-broken",
            current_level=3,
            successful_executions=5,
            success_rate=0.50,  # below 80%
            avg_confidence=0.30,  # well below threshold for L4 (0.85)
            last_execution_errors=3,  # above error_threshold (2)
            scope_violations=2,  # above scope_violation_threshold (1)
        )
        assert d.ready_to_promote is False
        assert d.confidence_score < 0.5
        assert len(d.issues) >= 3  # multiple gate failures

    def test_confidence_thresholds_escalate_by_level(self):
        """Each higher level requires a higher confidence threshold — verified against real TS.

        Replaces the old GATES dict structure test; exercises the actual
        confidence_threshold_per_level config in DEFAULT_SANDBOX_CONFIG.
        """
        # Values just below each level's confidence threshold should fail
        threshold_tests = [
            # (current_level, conf_just_below_threshold, expected_blocked)
            (0, 0.55, True),  # L1 threshold = 0.6
            (1, 0.65, True),  # L2 threshold = 0.7
            (2, 0.70, True),  # L3 threshold = 0.75
            (3, 0.80, True),  # L4 threshold = 0.85
            (4, 0.85, True),  # L5 threshold = 0.9
        ]
        for current_level, low_conf, expected_blocked in threshold_tests:
            d = _score(
                f"agent-conf-{current_level}",
                current_level=current_level,
                successful_executions=5,  # above min (3)
                success_rate=0.90,  # above 80%
                avg_confidence=low_conf,
                last_execution_errors=0,
                scope_violations=0,
            )
            assert d.ready_to_promote is (not expected_blocked), (
                f"L{current_level}->L{current_level + 1}: conf={low_conf} should "
                f"{'block' if expected_blocked else 'pass'}, got ready={d.ready_to_promote}"
            )
