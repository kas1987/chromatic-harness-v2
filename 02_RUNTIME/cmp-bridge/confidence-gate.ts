/**
 * Confidence Gate
 *
 * Uses magnet synthesis reports (post-execution) to decide if results
 * are confident enough to proceed with merge/deploy.
 *
 * This is the quality gate that prevents low-confidence work from advancing.
 */

import { SynthesisScore } from '../magnets/magnet-synthesis';

export interface ConfidenceGateResult {
  passed: boolean;
  reason: 'confident' | 'needs_review' | 'escalate' | 'blocked';
  synthesis_score: SynthesisScore;
  recommendation_override?: 'proceed' | 'review' | 'escalate' | 'blocked';
  notes: string[];
}

export class ConfidenceGate {
  private minConfidenceForProceed = 0.85;
  private minConfidenceForReview = 0.70;
  private minConfidenceForEscalate = 0.50;

  /**
   * Evaluate based on magnet synthesis
   */
  evaluate(synthesis: SynthesisScore): ConfidenceGateResult {
    const notes: string[] = [];
    let reason: 'confident' | 'needs_review' | 'escalate' | 'blocked' = 'confident';
    let passed = true;

    // Use synthesis recommendation as starting point
    let recommendation: 'proceed' | 'review' | 'escalate' | 'blocked' = synthesis.recommendation;

    // Critical anomalies always block
    if (synthesis.critical_anomalies > 0) {
      reason = 'blocked';
      passed = false;
      notes.push(`${synthesis.critical_anomalies} critical anomaly(ies) detected — must escalate`);
    }

    // High anomaly count escalates
    else if (synthesis.anomaly_count > 5) {
      reason = 'escalate';
      notes.push(`${synthesis.anomaly_count} anomalies detected — recommend human review`);
    }

    // Low confidence scores
    else if (synthesis.overall_confidence < this.minConfidenceForEscalate) {
      reason = 'blocked';
      passed = false;
      notes.push(
        `Overall confidence ${(synthesis.overall_confidence * 100).toFixed(0)}% below minimum ${(this.minConfidenceForEscalate * 100).toFixed(0)}%`
      );
    } else if (synthesis.overall_confidence < this.minConfidenceForReview) {
      reason = 'escalate';
      notes.push(
        `Overall confidence ${(synthesis.overall_confidence * 100).toFixed(0)}% — recommend review before proceeding`
      );
    } else if (synthesis.overall_confidence < this.minConfidenceForProceed) {
      reason = 'needs_review';
      notes.push(
        `Confidence ${(synthesis.overall_confidence * 100).toFixed(0)}% — brief review recommended`
      );
    }

    // Component-level checks
    if (synthesis.test_confidence < 0.6) {
      notes.push(
        `Test confidence low (${(synthesis.test_confidence * 100).toFixed(0)}%) — insufficient coverage`
      );
      if (reason === 'confident') reason = 'needs_review';
    }

    if (synthesis.execution_quality < 0.7) {
      notes.push(`Execution quality concerns (${(synthesis.execution_quality * 100).toFixed(0)}%)`);
      if (reason === 'confident') reason = 'needs_review';
    }

    if (synthesis.cost_efficiency < 0.5) {
      notes.push(
        `Cost efficiency poor (${(synthesis.cost_efficiency * 100).toFixed(0)}%) — budget overrun or inefficient execution`
      );
    }

    return {
      passed,
      reason,
      synthesis_score: synthesis,
      recommendation_override: recommendation,
      notes,
    };
  }

  /**
   * Generate human-readable report
   */
  formatResult(result: ConfidenceGateResult): string {
    const lines: string[] = [];
    const verdict = result.passed ? '✅ PASS' : '❌ FAIL';

    lines.push(verdict);
    lines.push(`Reason: ${result.reason.toUpperCase()}`);
    lines.push('');
    lines.push(`Overall Confidence: ${(result.synthesis_score.overall_confidence * 100).toFixed(0)}%`);
    lines.push(`  • Execution: ${(result.synthesis_score.execution_quality * 100).toFixed(0)}%`);
    lines.push(`  • Cost:      ${(result.synthesis_score.cost_efficiency * 100).toFixed(0)}%`);
    lines.push(`  • Tests:     ${(result.synthesis_score.test_confidence * 100).toFixed(0)}%`);
    lines.push('');
    lines.push(
      `Anomalies: ${result.synthesis_score.anomaly_count} (${result.synthesis_score.critical_anomalies} critical)`
    );

    if (result.notes.length > 0) {
      lines.push('');
      lines.push('Notes:');
      for (const note of result.notes) {
        lines.push(`  • ${note}`);
      }
    }

    lines.push('');
    lines.push(`Recommendation: ${result.recommendation_override?.toUpperCase()}`);

    return lines.join('\n');
  }

  /**
   * Set custom confidence thresholds
   */
  setThresholds(
    proceed: number,
    review: number,
    escalate: number
  ): void {
    this.minConfidenceForProceed = proceed;
    this.minConfidenceForReview = review;
    this.minConfidenceForEscalate = escalate;
  }
}
