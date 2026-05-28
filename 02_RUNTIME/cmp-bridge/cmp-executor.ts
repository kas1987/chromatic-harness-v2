/**
 * CMP Executor
 *
 * Orchestrates the governance flow:
 * 1. IntentGate: Is the goal clear?
 * 2. ScopeGate: Is file access appropriate?
 * 3. ConfidenceGate (post-execution): Are results high-quality?
 *
 * Returns a mission approval/rejection with detailed reasoning.
 */

import { MissionPacket, ExecutionResult } from '../../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';
import { SynthesisScore, MagnetSynthesis } from '../magnets/magnet-synthesis';
import { IntentGate, IntentGateResult } from './intent-gate';
import { ScopeGate, ScopeGateResult } from './scope-gate';
import { ConfidenceGate, ConfidenceGateResult } from './confidence-gate';

export interface GateResults {
  intent: IntentGateResult;
  scope: ScopeGateResult;
  confidence?: ConfidenceGateResult;
}

export interface MissionApproval {
  mission_id: string;
  approved: boolean;
  stage: 'intake' | 'execution' | 'completion';
  gate_results: GateResults;
  recommendation: 'proceed' | 'review' | 'escalate' | 'blocked';
  escalation_reason?: string;
  notes: string[];
}

export class CMPExecutor {
  private intentGate: IntentGate;
  private scopeGate: ScopeGate;
  private confidenceGate: ConfidenceGate;

  constructor() {
    this.intentGate = new IntentGate();
    this.scopeGate = new ScopeGate();
    this.confidenceGate = new ConfidenceGate();
  }

  /**
   * Evaluate a mission packet at intake (before execution)
   */
  evaluateIntake(packet: MissionPacket): MissionApproval {
    const intentResult = this.intentGate.evaluate(packet);
    const scopeResult = this.scopeGate.evaluate(packet);

    const notes: string[] = [];
    let approved = true;
    let recommendation: 'proceed' | 'review' | 'escalate' | 'blocked' = 'proceed';

    // If any required gate fails, block
    if (packet.required_gates.includes('intent') && !intentResult.passed) {
      approved = false;
      recommendation = 'blocked';
      notes.push('Intent gate failed; clarify goal before proceeding');
    }

    if (packet.required_gates.includes('scope') && !scopeResult.passed) {
      approved = false;
      recommendation = 'blocked';
      if (scopeResult.forbidden_conflicts.length > 0) {
        notes.push('Scope conflicts with forbidden paths');
      }
      notes.push('Adjust scope and resubmit');
    }

    // If optional gates have concerns, recommend review
    if (!intentResult.passed && !packet.required_gates.includes('intent')) {
      if (recommendation === 'proceed') recommendation = 'review';
      notes.push('Intent clarity could be improved');
    }

    if (!scopeResult.passed && !packet.required_gates.includes('scope')) {
      if (recommendation === 'proceed') recommendation = 'review';
      notes.push('Scope has some concerns but not blocking');
    }

    return {
      mission_id: packet.mission_id,
      approved,
      stage: 'intake',
      gate_results: {
        intent: intentResult,
        scope: scopeResult,
      },
      recommendation,
      notes,
    };
  }

  /**
   * Evaluate execution result (post-execution, uses magnet reports)
   */
  evaluateCompletion(
    packet: MissionPacket,
    result: ExecutionResult,
    synthesis: SynthesisScore
  ): MissionApproval {
    const confidenceResult = this.confidenceGate.evaluate(synthesis);

    const notes: string[] = [];
    let approved = confidenceResult.passed;
    let recommendation = confidenceResult.recommendation_override || synthesis.recommendation;
    let escalation_reason: string | undefined;

    // Check if confidence gate is required
    if (packet.required_gates.includes('confidence')) {
      if (!confidenceResult.passed) {
        approved = false;
        escalation_reason = `Confidence gate failed: ${confidenceResult.reason}`;
        recommendation = 'blocked';
      }
    } else if (confidenceResult.reason !== 'confident') {
      // Optional confidence concerns
      approved = false; // Don't auto-approve without confidence
      recommendation = confidenceResult.reason as any;
    }

    // Add detailed notes from confidence evaluation
    notes.push(...confidenceResult.notes);

    // Check for high anomaly counts
    if (synthesis.critical_anomalies > 0) {
      escalation_reason = `${synthesis.critical_anomalies} critical issue(s) detected`;
      recommendation = 'blocked';
      approved = false;
    }

    return {
      mission_id: packet.mission_id,
      approved,
      stage: 'completion',
      gate_results: {
        intent: { passed: true, clarity_score: 1.0, issues: [], suggestions: [] }, // Re-use from intake
        scope: { passed: true, coverage_score: 1.0, issues: [], warnings: [], forbidden_conflicts: [] },
        confidence: confidenceResult,
      },
      recommendation,
      escalation_reason,
      notes,
    };
  }

  /**
   * Format approval decision for human readability
   */
  formatApproval(approval: MissionApproval): string {
    const lines: string[] = [];

    lines.push('═══════════════════════════════════════');
    lines.push('MISSION APPROVAL DECISION');
    lines.push('═══════════════════════════════════════');
    lines.push('');
    lines.push(`Mission: ${approval.mission_id}`);
    lines.push(`Stage: ${approval.stage}`);
    lines.push('');

    const verdict = approval.approved ? '✅ APPROVED' : '❌ REJECTED';
    lines.push(verdict);
    lines.push(`Recommendation: ${approval.recommendation.toUpperCase()}`);

    if (approval.escalation_reason) {
      lines.push(`Escalation: ${approval.escalation_reason}`);
    }

    lines.push('');
    lines.push('Gate Results:');

    if (approval.gate_results.intent) {
      const intent = approval.gate_results.intent;
      lines.push(`  [Intent] ${intent.passed ? '✓' : '✗'} (${(intent.clarity_score * 100).toFixed(0)}%)`);
    }

    if (approval.gate_results.scope) {
      const scope = approval.gate_results.scope;
      lines.push(
        `  [Scope]  ${scope.passed ? '✓' : '✗'} (${(scope.coverage_score * 100).toFixed(0)}%)`
      );
    }

    if (approval.gate_results.confidence) {
      const conf = approval.gate_results.confidence;
      lines.push(
        `  [Confidence] ${conf.passed ? '✓' : '✗'} (${(conf.synthesis_score.overall_confidence * 100).toFixed(0)}%)`
      );
    }

    if (approval.notes.length > 0) {
      lines.push('');
      lines.push('Notes:');
      for (const note of approval.notes) {
        lines.push(`  • ${note}`);
      }
    }

    lines.push('');
    lines.push('═══════════════════════════════════════');

    return lines.join('\n');
  }
}
