/**
 * Magnet Synthesis
 *
 * Aggregates all magnet reports into a unified execution quality score
 * and decision signals for downstream gates (CMP, Console, Beads).
 */

import { MagnetReport } from '../../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';

export interface SynthesisScore {
  overall_confidence: number; // 0-1, weighted average
  execution_quality: number; // 0-1, execution magnet
  cost_efficiency: number; // 0-1, cost magnet
  test_confidence: number; // 0-1, confidence magnet
  anomaly_count: number; // Total anomalies across all magnets
  critical_anomalies: number; // Errors that require escalation
  recommendation: 'proceed' | 'review' | 'escalate' | 'blocked';
}

export class MagnetSynthesis {
  private reports: Map<string, MagnetReport> = new Map();

  /**
   * Add a magnet report
   */
  addReport(report: MagnetReport): void {
    this.reports.set(report.magnet_type, report);
  }

  /**
   * Synthesize all reports into a unified score and recommendation
   */
  synthesize(): SynthesisScore {
    const scores = Array.from(this.reports.values()).map((r) => r.score);
    const overallConfidence =
      scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0.5;

    const executionQuality = this.reports.get('execution')?.score ?? 0.5;
    const costEfficiency = this.reports.get('cost')?.score ?? 0.5;
    const testConfidence = this.reports.get('confidence')?.score ?? 0.5;

    const allAnomalies = Array.from(this.reports.values()).flatMap((r) => r.anomalies);
    const anomalyCount = allAnomalies.length;
    const criticalAnomalies = allAnomalies.filter((a) => a.level === 'error').length;

    // Determine recommendation based on anomalies and scores
    let recommendation: 'proceed' | 'review' | 'escalate' | 'blocked' = 'proceed';

    if (criticalAnomalies > 0) {
      recommendation = 'blocked';
    } else if (anomalyCount > 5) {
      recommendation = 'escalate';
    } else if (anomalyCount > 0 || overallConfidence < 0.75) {
      recommendation = 'review';
    }

    // Boost confidence if all quality gates pass
    let adjustedConfidence = overallConfidence;
    if (testConfidence > 0.9 && executionQuality > 0.9 && costEfficiency > 0.9) {
      adjustedConfidence = Math.min(1.0, adjustedConfidence + 0.1);
    }

    return {
      overall_confidence: Math.round(adjustedConfidence * 100) / 100,
      execution_quality: Math.round(executionQuality * 100) / 100,
      cost_efficiency: Math.round(costEfficiency * 100) / 100,
      test_confidence: Math.round(testConfidence * 100) / 100,
      anomaly_count: anomalyCount,
      critical_anomalies: criticalAnomalies,
      recommendation,
    };
  }

  /**
   * Generate a human-readable synthesis report
   */
  report(): string {
    const synthesis = this.synthesize();
    const lines: string[] = [];

    lines.push('═══════════════════════════════════════');
    lines.push('MAGNET SYNTHESIS REPORT');
    lines.push('═══════════════════════════════════════');
    lines.push('');
    lines.push(`Overall Confidence:  ${(synthesis.overall_confidence * 100).toFixed(0)}%`);
    lines.push(`Execution Quality:   ${(synthesis.execution_quality * 100).toFixed(0)}%`);
    lines.push(`Cost Efficiency:     ${(synthesis.cost_efficiency * 100).toFixed(0)}%`);
    lines.push(`Test Confidence:     ${(synthesis.test_confidence * 100).toFixed(0)}%`);
    lines.push('');
    lines.push(`Anomalies Detected:  ${synthesis.anomaly_count}`);
    lines.push(`  Critical (errors): ${synthesis.critical_anomalies}`);
    lines.push(`  Warnings:          ${synthesis.anomaly_count - synthesis.critical_anomalies}`);
    lines.push('');
    lines.push(`RECOMMENDATION:      ${synthesis.recommendation.toUpperCase()}`);
    lines.push('');

    if (synthesis.recommendation === 'blocked') {
      lines.push('⛔ BLOCKED: Critical issues must be resolved before proceeding.');
    } else if (synthesis.recommendation === 'escalate') {
      lines.push('🔴 ESCALATE: Multiple issues detected. Recommend human review.');
    } else if (synthesis.recommendation === 'review') {
      lines.push('🟡 REVIEW: Some concerns. Recommend brief review before proceeding.');
    } else {
      lines.push('✅ PROCEED: Confidence thresholds met. Safe to proceed.');
    }

    lines.push('');
    lines.push('Detailed magnet reports:');
    for (const [magnet_type, report] of this.reports) {
      lines.push(`\n  [${magnet_type.toUpperCase()}]`);
      lines.push(`    Score: ${(report.score * 100).toFixed(0)}%`);
      if (report.anomalies.length > 0) {
        lines.push(`    Anomalies: ${report.anomalies.length}`);
        for (const anom of report.anomalies.slice(0, 3)) {
          lines.push(`      - [${anom.level}] ${anom.message}`);
        }
        if (report.anomalies.length > 3) {
          lines.push(`      ... and ${report.anomalies.length - 3} more`);
        }
      }
    }

    lines.push('');
    lines.push('═══════════════════════════════════════');

    return lines.join('\n');
  }

  /**
   * Reset all reports
   */
  reset(): void {
    this.reports.clear();
  }

  /**
   * Get raw synthesis score (for API/programmatic access)
   */
  getScore(): SynthesisScore {
    return this.synthesize();
  }
}
