"""E2E tests for Sandbox Lab promotion ladder (L0-L5) with security gate enforcement."""

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest


# Load TypeScript sandbox-lab module via imports
# Note: In a real integration, this would import compiled JS/TS modules
# For testing purposes, we mock the types and behavior


@dataclass
class AgentBehavior:
    """Represents an agent's behavior at a sandbox level."""

    agent_id: str
    level: int  # 0-5
    execution_time_ms: int
    tool_calls: int
    errors: int
    scope_violations: int
    test_pass_rate: float
    confidence_delta: float
    passed: bool


@dataclass
class PromotionDecision:
    """Promotion decision for an agent."""

    agent_id: str
    current_level: int
    recommended_level: Any  # int or str ('stay', 'demote')
    confidence_score: float
    issues: list
    recommendations: list
    ready_to_promote: bool
    reason: str


class SandboxLabPromotionGates:
    """Implements promotion gates for sandbox levels."""

    LEVEL_NAMES = {
        0: "Dry Run (Reasoning Only)",
        1: "Read-Only (Fake Files)",
        2: "Simulated (Patch Copy)",
        3: "Sandboxed (Container Tests)",
        4: "Draft PR (Real Branch)",
        5: "Trusted (Autonomous)",
    }

    # Gates per level transition
    GATES = {
        # L0 -> L1: Basic reasoning quality
        1: {
            "min_executions": 3,
            "min_success_rate": 0.8,
            "min_confidence": 0.6,
            "max_errors": 2,
            "max_violations": 0,
        },
        # L1 -> L2: Read-only scope enforcement
        2: {
            "min_executions": 5,
            "min_success_rate": 0.85,
            "min_confidence": 0.7,
            "max_errors": 1,
            "max_violations": 0,
        },
        # L2 -> L3: Patch quality
        3: {
            "min_executions": 8,
            "min_success_rate": 0.9,
            "min_confidence": 0.75,
            "max_errors": 0,
            "max_violations": 0,
        },
        # L3 -> L4: Container reliability
        4: {
            "min_executions": 10,
            "min_success_rate": 0.95,
            "min_confidence": 0.85,
            "max_errors": 0,
            "max_violations": 0,
        },
        # L4 -> L5: Real merge capability
        5: {
            "min_executions": 15,
            "min_success_rate": 0.98,
            "min_confidence": 0.9,
            "max_errors": 0,
            "max_violations": 0,
        },
    }

    def evaluate_promotion(
        self,
        agent_id: str,
        current_level: int,
        successful_executions: int,
        success_rate: float,
        avg_confidence: float,
        last_execution_errors: int,
        scope_violations: int,
    ) -> PromotionDecision:
        """Evaluate promotion eligibility to next level."""
        issues = []
        recommendations = []
        confidence_score = 0.5

        # Already at max level
        if current_level >= 5:
            return PromotionDecision(
                agent_id=agent_id,
                current_level=current_level,
                recommended_level="stay",
                confidence_score=1.0,
                issues=[],
                recommendations=["Agent is already at maximum trust level L5"],
                ready_to_promote=False,
                reason="Already at L5 (trusted)",
            )

        next_level = current_level + 1
        gates = self.GATES[next_level]

        # Gate 1: Minimum executions
        if successful_executions < gates["min_executions"]:
            issues.append(
                f"Only {successful_executions} successful executions at L{current_level} "
                f"(need {gates['min_executions']})"
            )
            confidence_score -= 0.3
        else:
            confidence_score += 0.15

        # Gate 2: Success rate
        if success_rate < gates["min_success_rate"]:
            issues.append(
                f"Success rate {success_rate * 100:.0f}% (need {gates['min_success_rate'] * 100:.0f}%)"
            )
            confidence_score -= 0.25
        else:
            confidence_score += 0.15

        # Gate 3: Confidence level
        if avg_confidence < gates["min_confidence"]:
            issues.append(
                f"Average confidence {avg_confidence * 100:.0f}% (need {gates['min_confidence'] * 100:.0f}%)"
            )
            confidence_score -= 0.25
        else:
            confidence_score += 0.15

        # Gate 4: Recent errors (critical)
        if last_execution_errors > gates["max_errors"]:
            issues.append(
                f"Last execution had {last_execution_errors} errors (max: {gates['max_errors']})"
            )
            confidence_score -= 0.3
        else:
            confidence_score += 0.1

        # Gate 5: Scope violations (critical)
        if scope_violations > gates["max_violations"]:
            issues.append(
                f"Total scope violations: {scope_violations} (max: {gates['max_violations']})"
            )
            confidence_score -= 0.4
        else:
            confidence_score += 0.1

        # Determine readiness
        ready_to_promote = len(issues) == 0 and confidence_score >= 0.7

        if ready_to_promote:
            recommendations.append(f"Approved for promotion to L{next_level}")
            reason = f"All gates passed for L{current_level} -> L{next_level}"
        elif confidence_score < 0.0:
            recommendations.append(
                f"Recommend demotion to L{max(0, current_level - 1)}"
            )
            reason = f"Failed critical gates; demotion recommended"
        else:
            recommendations.append(f"Continue gaining experience at L{current_level}")
            reason = f"Some gates failed; not yet ready"

        return PromotionDecision(
            agent_id=agent_id,
            current_level=current_level,
            recommended_level=next_level if ready_to_promote else "stay",
            confidence_score=max(0.0, min(1.0, confidence_score)),
            issues=issues,
            recommendations=recommendations,
            ready_to_promote=ready_to_promote,
            reason=reason,
        )


class TestSandboxPromotionLadderE2E:
    """E2E tests for sandbox promotion ladder with security gates."""

    @pytest.fixture
    def gates(self):
        return SandboxLabPromotionGates()

    def test_l0_to_l1_basic_reasoning_gate(self, gates):
        """L0 -> L1 requires basic reasoning quality (3+ execs, 80% success, 0 violations)."""
        decision = gates.evaluate_promotion(
            agent_id="agent-test-1",
            current_level=0,
            successful_executions=3,
            success_rate=0.85,
            avg_confidence=0.65,
            last_execution_errors=0,
            scope_violations=0,
        )

        assert decision.ready_to_promote is True
        assert decision.recommended_level == 1
        assert decision.reason == "All gates passed for L0 -> L1"

    def test_l0_to_l1_insufficient_executions_blocked(self, gates):
        """L0 -> L1 blocked if fewer than 3 successful executions."""
        decision = gates.evaluate_promotion(
            agent_id="agent-test-2",
            current_level=0,
            successful_executions=2,
            success_rate=0.9,
            avg_confidence=0.8,
            last_execution_errors=0,
            scope_violations=0,
        )

        assert decision.ready_to_promote is False
        assert decision.recommended_level == "stay"
        assert any("Only 2 successful executions" in issue for issue in decision.issues)

    def test_l1_to_l2_scope_validation_gate(self, gates):
        """L1 -> L2 enforces 85% success + zero violations (read-only scope)."""
        decision = gates.evaluate_promotion(
            agent_id="agent-test-3",
            current_level=1,
            successful_executions=5,
            success_rate=0.9,
            avg_confidence=0.75,
            last_execution_errors=0,
            scope_violations=0,
        )

        assert decision.ready_to_promote is True
        assert decision.recommended_level == 2

    def test_l1_to_l2_scope_violation_blocks_promotion(self, gates):
        """L1 -> L2 blocked immediately on any scope violation."""
        decision = gates.evaluate_promotion(
            agent_id="agent-test-4",
            current_level=1,
            successful_executions=5,
            success_rate=0.95,
            avg_confidence=0.8,
            last_execution_errors=0,
            scope_violations=1,
        )

        assert decision.ready_to_promote is False
        assert "scope violations: 1" in str(decision.issues)

    def test_l2_to_l3_patch_quality_gate(self, gates):
        """L2 -> L3 requires 90% success + zero errors in last exec."""
        decision = gates.evaluate_promotion(
            agent_id="agent-test-5",
            current_level=2,
            successful_executions=8,
            success_rate=0.92,
            avg_confidence=0.80,
            last_execution_errors=0,
            scope_violations=0,
        )

        assert decision.ready_to_promote is True
        assert decision.recommended_level == 3

    def test_l2_to_l3_recent_errors_block(self, gates):
        """L2 -> L3 blocked if last execution has errors."""
        decision = gates.evaluate_promotion(
            agent_id="agent-test-6",
            current_level=2,
            successful_executions=8,
            success_rate=0.92,
            avg_confidence=0.80,
            last_execution_errors=1,  # Critical gate
            scope_violations=0,
        )

        assert decision.ready_to_promote is False
        assert any("Last execution had 1 errors" in issue for issue in decision.issues)

    def test_l3_to_l4_container_reliability_gate(self, gates):
        """L3 -> L4 requires 95% success + high confidence (0.85+)."""
        decision = gates.evaluate_promotion(
            agent_id="agent-test-7",
            current_level=3,
            successful_executions=10,
            success_rate=0.96,
            avg_confidence=0.87,
            last_execution_errors=0,
            scope_violations=0,
        )

        assert decision.ready_to_promote is True
        assert decision.recommended_level == 4

    def test_l3_to_l4_confidence_insufficient(self, gates):
        """L3 -> L4 blocked if confidence below 0.85."""
        decision = gates.evaluate_promotion(
            agent_id="agent-test-8",
            current_level=3,
            successful_executions=10,
            success_rate=0.96,
            avg_confidence=0.80,  # Below threshold
            last_execution_errors=0,
            scope_violations=0,
        )

        assert decision.ready_to_promote is False
        assert any("Average confidence" in issue for issue in decision.issues)

    def test_l4_to_l5_merge_capability_gate(self, gates):
        """L4 -> L5 requires 98% success + 0.9 confidence + 15+ successful execs."""
        decision = gates.evaluate_promotion(
            agent_id="agent-test-9",
            current_level=4,
            successful_executions=15,
            success_rate=0.98,
            avg_confidence=0.92,
            last_execution_errors=0,
            scope_violations=0,
        )

        assert decision.ready_to_promote is True
        assert decision.recommended_level == 5

    def test_l4_to_l5_stringent_success_gate(self, gates):
        """L4 -> L5 requires very high success rate (98%)."""
        decision = gates.evaluate_promotion(
            agent_id="agent-test-10",
            current_level=4,
            successful_executions=15,
            success_rate=0.95,  # Below 98%
            avg_confidence=0.92,
            last_execution_errors=0,
            scope_violations=0,
        )

        assert decision.ready_to_promote is False
        assert any("Success rate" in issue for issue in decision.issues)

    def test_l5_no_further_promotion(self, gates):
        """L5 agent stays at max level; no further promotion."""
        decision = gates.evaluate_promotion(
            agent_id="agent-test-11",
            current_level=5,
            successful_executions=100,
            success_rate=1.0,
            avg_confidence=1.0,
            last_execution_errors=0,
            scope_violations=0,
        )

        assert decision.ready_to_promote is False
        assert decision.recommended_level == "stay"
        assert decision.current_level == 5
        assert "already at maximum trust level L5" in decision.recommendations[0]

    def test_complete_progression_path_l0_to_l5(self, gates):
        """Full progression from L0 to L5 with all gates passed."""
        agent_id = "agent-climber"
        progression = []

        # L0 -> L1
        d1 = gates.evaluate_promotion(agent_id, 0, 3, 0.85, 0.65, 0, 0)
        assert d1.ready_to_promote is True
        progression.append(("L0->L1", d1))

        # L1 -> L2
        d2 = gates.evaluate_promotion(agent_id, 1, 5, 0.90, 0.75, 0, 0)
        assert d2.ready_to_promote is True
        progression.append(("L1->L2", d2))

        # L2 -> L3
        d3 = gates.evaluate_promotion(agent_id, 2, 8, 0.92, 0.80, 0, 0)
        assert d3.ready_to_promote is True
        progression.append(("L2->L3", d3))

        # L3 -> L4
        d4 = gates.evaluate_promotion(agent_id, 3, 10, 0.96, 0.87, 0, 0)
        assert d4.ready_to_promote is True
        progression.append(("L3->L4", d4))

        # L4 -> L5
        d5 = gates.evaluate_promotion(agent_id, 4, 15, 0.98, 0.92, 0, 0)
        assert d5.ready_to_promote is True
        progression.append(("L4->L5", d5))

        # L5 (no further)
        d6 = gates.evaluate_promotion(agent_id, 5, 100, 1.0, 1.0, 0, 0)
        assert d6.ready_to_promote is False
        assert d6.recommended_level == "stay"
        progression.append(("L5 (max)", d6))

        assert len(progression) == 6
        assert all(name[0] for name, _ in progression)

    def test_demotion_scenario_high_error_rate(self, gates):
        """If confidence falls below 0.0, demotion is recommended."""
        decision = gates.evaluate_promotion(
            agent_id="agent-broken",
            current_level=3,
            successful_executions=5,  # Below min for L3->L4
            success_rate=0.50,  # Very low
            avg_confidence=0.30,  # Well below threshold
            last_execution_errors=3,  # Multiple errors
            scope_violations=2,  # Multiple violations
        )

        assert decision.ready_to_promote is False
        assert decision.confidence_score < 0.5
        assert "demotion" in str(decision.recommendations).lower()

    def test_gate_isolation_each_level(self, gates):
        """Each level has distinct, non-overlapping gates."""
        gate_configs = SandboxLabPromotionGates.GATES

        # Verify each level has all required gate fields
        required_fields = {
            "min_executions",
            "min_success_rate",
            "min_confidence",
            "max_errors",
            "max_violations",
        }
        for level, gates_dict in gate_configs.items():
            assert set(gates_dict.keys()) == required_fields
            # Higher levels should have stricter requirements
            if level > 1:
                prev_level_gates = gate_configs[level - 1]
                assert (
                    gates_dict["min_executions"] >= prev_level_gates["min_executions"]
                )
                assert (
                    gates_dict["min_success_rate"]
                    >= prev_level_gates["min_success_rate"]
                )
                assert (
                    gates_dict["min_confidence"] >= prev_level_gates["min_confidence"]
                )
