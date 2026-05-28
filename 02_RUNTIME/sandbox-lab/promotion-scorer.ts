/**
 * Promotion Scorer
 *
 * Evaluates whether an agent should be promoted to the next sandbox level.
 * Considers execution history, confidence trends, and violation patterns.
 */

import {
  SandboxLevel,
  AgentBehavior,
  PromotionDecision,
  AgentTrustProfile,
  SandboxLabConfig,
  DEFAULT_SANDBOX_CONFIG,
} from './sandbox-types';

export class PromotionScorer {
  private config: SandboxLabConfig;

  constructor(config?: Partial<SandboxLabConfig>) {
    this.config = { ...DEFAULT_SANDBOX_CONFIG, ...config };
  }

  /**
   * Score an agent's readiness for promotion
   */
  scorePromotion(
    agent_id: string,
    current_level: SandboxLevel,
    profile: AgentTrustProfile,
    last_behavior: AgentBehavior
  ): PromotionDecision {
    const issues: string[] = [];
    const recommendations: string[] = [];
    let confidenceScore = 0.5;

    // Already at L5
    if (current_level === 5) {
      return {
        agent_id,
        current_level,
        recommended_level: 'stay',
        confidence_score: 1.0,
        issues: [],
        recommendations: ['Agent is already at maximum trust level'],
        ready_to_promote: false,
        reason: 'Already at L5 (trusted)',
      };
    }

    // Check execution count
    const targetLevel = (current_level + 1) as SandboxLevel;
    if (
      profile.successful_executions < this.config.min_executions_per_level
    ) {
      issues.push(
        `Only ${profile.successful_executions} successful executions at L${current_level} (need ${this.config.min_executions_per_level})`
      );
      confidenceScore -= 0.3;
    }

    // Check recent violations
    if (profile.last_violation && profile.last_violation.level === current_level) {
      const daysSinceViolation = (Date.now() - profile.last_violation.date) / (1000 * 60 * 60 * 24);
      if (daysSinceViolation < 7) {
        issues.push(
          `Recent violation ${daysSinceViolation.toFixed(1)} days ago (${profile.last_violation.violation_type})`
        );
        confidenceScore -= 0.4;
      } else {
        recommendations.push(`Violation was ${daysSinceViolation.toFixed(0)} days ago - pattern resolved`);
      }
    }

    // Check success rate
    if (profile.success_rate < 0.8) {
      issues.push(`Success rate ${(profile.success_rate * 100).toFixed(0)}% (need 80%)`);
      confidenceScore -= 0.2;
    } else {
      confidenceScore += 0.15;
    }

    // Check average confidence
    const requiredConfidence = this.config.confidence_threshold_per_level[targetLevel];
    if (profile.avg_confidence < requiredConfidence) {
      issues.push(
        `Average confidence ${(profile.avg_confidence * 100).toFixed(0)}% (need ${(requiredConfidence * 100).toFixed(0)}%)`
      );
      confidenceScore -= 0.25;
    } else {
      confidenceScore += 0.2;
    }

    // Check last behavior
    if (last_behavior.errors > this.config.error_threshold) {
      issues.push(
        `Last execution had ${last_behavior.errors} errors (threshold: ${this.config.error_threshold})`
      );
      confidenceScore -= 0.1;
    } else if (last_behavior.errors === 0) {
      confidenceScore += 0.1;
    }

    if (last_behavior.scope_violations > this.config.scope_violation_threshold) {
      issues.push(
        `Scope violations in last run (${last_behavior.scope_violations} violations)`
      );
      confidenceScore -= 0.15;
    }

    // Check risk score
    if (profile.risk_score > 0.4) {
      issues.push(`High risk score: ${(profile.risk_score * 100).toFixed(0)}%`);
      confidenceScore -= 0.15;
    }

    // Check trend (improvement vs regression)
    const trend = this.analyzeExecutionTrend(profile);
    if (trend === 'improving') {
      recommendations.push('Agent showing improvement trend');
      confidenceScore += 0.1;
    } else if (trend === 'declining') {
      issues.push('Agent showing performance decline');
      confidenceScore -= 0.2;
    }

    confidenceScore = Math.max(0, Math.min(1, confidenceScore));

    const readyToPromote = issues.length === 0 && confidenceScore >= 0.7;

    return {
      agent_id,
      current_level,
      recommended_level: readyToPromote ? targetLevel : 'stay',
      confidence_score: confidenceScore,
      issues,
      recommendations,
      ready_to_promote: readyToPromote,
      reason: this.generateReason(
        readyToPromote,
        current_level,
        issues.length,
        confidenceScore
      ),
    };
  }

  /**
   * Analyze execution trend
   */
  private analyzeExecutionTrend(
    profile: AgentTrustProfile
  ): 'improving' | 'stable' | 'declining' | 'insufficient_data' {
    if (profile.promotion_history.length < 2) {
      return 'insufficient_data';
    }

    const recent = profile.promotion_history.slice(-3);
    const successRates = recent.map((p) => {
      // Estimate success rate based on level reached
      return 1 - p.level / 10; // Rough heuristic
    });

    const trend = successRates[successRates.length - 1] - successRates[0];

    if (trend > 0.1) return 'improving';
    if (trend < -0.1) return 'declining';
    return 'stable';
  }

  /**
   * Generate human-readable reason
   */
  private generateReason(
    readyToPromote: boolean,
    level: SandboxLevel,
    issueCount: number,
    score: number
  ): string {
    if (readyToPromote) {
      return `Agent meets all criteria for L${level + 1} promotion (confidence: ${(score * 100).toFixed(0)}%)`;
    }

    if (issueCount > 3) {
      return `Multiple concerns prevent promotion (${issueCount} issues, confidence: ${(score * 100).toFixed(0)}%)`;
    }

    if (score < 0.5) {
      return `Low confidence score (${(score * 100).toFixed(0)}%) - more execution history needed`;
    }

    return `Agent not yet ready for promotion (${issueCount} issue(s) to resolve)`;
  }

  /**
   * Evaluate if agent should be demoted
   */
  evaluateDemotion(
    agent_id: string,
    profile: AgentTrustProfile,
    last_behavior: AgentBehavior
  ): {
    should_demote: boolean;
    reason: string;
    target_level?: SandboxLevel;
  } {
    // Critical violations
    if (last_behavior.errors > this.config.error_threshold * 2) {
      return {
        should_demote: true,
        reason: `Critical errors (${last_behavior.errors}) - demote 1 level`,
        target_level: Math.max(0, profile.current_level - 1) as SandboxLevel,
      };
    }

    if (last_behavior.scope_violations > 0) {
      return {
        should_demote: true,
        reason: 'Scope violation detected - demote 2 levels',
        target_level: Math.max(0, profile.current_level - 2) as SandboxLevel,
      };
    }

    // Declining success rate
    if (profile.success_rate < 0.5) {
      return {
        should_demote: true,
        reason: `Low success rate (${(profile.success_rate * 100).toFixed(0)}%) - demote 1 level`,
        target_level: Math.max(0, profile.current_level - 1) as SandboxLevel,
      };
    }

    return {
      should_demote: false,
      reason: 'No demotion needed',
    };
  }

  /**
   * Format promotion decision for display
   */
  formatDecision(decision: PromotionDecision): string {
    const lines: string[] = [];

    lines.push('═════════════════════════════════════════');
    lines.push('PROMOTION DECISION');
    lines.push('═════════════════════════════════════════');
    lines.push('');
    lines.push(`Agent: ${decision.agent_id}`);
    lines.push(`Current Level: L${decision.current_level}`);
    lines.push(`Confidence Score: ${(decision.confidence_score * 100).toFixed(0)}%`);
    lines.push('');

    const verdict = decision.ready_to_promote ? '✅ READY TO PROMOTE' : '⏸ NOT READY';
    lines.push(verdict);

    if (decision.recommended_level !== 'stay') {
      lines.push(`Recommended: L${decision.recommended_level}`);
    }

    lines.push('');
    lines.push(`Reason: ${decision.reason}`);
    lines.push('');

    if (decision.issues.length > 0) {
      lines.push('Issues:');
      for (const issue of decision.issues) {
        lines.push(`  • ${issue}`);
      }
      lines.push('');
    }

    if (decision.recommendations.length > 0) {
      lines.push('Recommendations:');
      for (const rec of decision.recommendations) {
        lines.push(`  ✓ ${rec}`);
      }
      lines.push('');
    }

    lines.push('═════════════════════════════════════════');

    return lines.join('\n');
  }
}
