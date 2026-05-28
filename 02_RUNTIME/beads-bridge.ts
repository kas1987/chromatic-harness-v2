/**
 * Beads Bridge
 *
 * Converts roach-pi execution results + magnet reports into Chromatic Beads.
 *
 * Beads are structured action/alert/learning/score objects that flow into:
 * - Action queue (what to do next)
 * - Alert dashboard (what went wrong)
 * - Memory system (what we learned)
 * - Confidence tracker (evidence for future work)
 */

import { ExecutionResult, Learning, MagnetReport } from '../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';

/**
 * A Bead is a structured unit of work or information flowing through Chromatic
 */
export interface Bead {
  id: string;
  type: 'action' | 'alert' | 'learning' | 'score';
  status: 'pending' | 'in_progress' | 'completed' | 'waiting';
  title: string;
  description?: string;
  context?: Record<string, any>;
  tags?: string[];
  priority?: number; // 0-4; 0 = critical
  source: {
    runtime: string;
    mission_id: string;
    stage: 'execution' | 'validation' | 'synthesis';
  };
  evidence?: Record<string, any>;
  created_at: number;
  due_by?: number;
}

export class BeadsBridge {
  /**
   * Convert roach-pi execution result into action beads
   */
  executionToBeads(result: ExecutionResult): Bead[] {
    const beads: Bead[] = [];

    // Closed tasks → Action Beads (completed work)
    for (const task of result.output.closed_tasks) {
      beads.push({
        id: `action-${result.mission_id}-${task.id}`,
        type: 'action',
        status: 'completed',
        title: task.title,
        description: task.description,
        context: { task_id: task.id, task_status: task.status },
        tags: ['completed', 'task', task.status],
        priority: 4,
        source: {
          runtime: 'roach-pi',
          mission_id: result.mission_id,
          stage: 'execution',
        },
        evidence: task.evidence,
        created_at: Date.now(),
      });
    }

    // Blocked tasks → Action Beads (follow-up work)
    for (const task of result.output.blocked_tasks) {
      beads.push({
        id: `action-${result.mission_id}-${task.id}-blocked`,
        type: 'action',
        status: 'waiting',
        title: `Follow-up: ${task.title || 'Unblock task'}`,
        description: `Blocked on: ${task.blocked_on || 'unknown'}`,
        context: {
          blocked_task_id: task.id,
          blocked_on: task.blocked_on,
        },
        tags: ['follow-up', 'blocked'],
        priority: 1, // Medium priority
        source: {
          runtime: 'roach-pi',
          mission_id: result.mission_id,
          stage: 'execution',
        },
        created_at: Date.now(),
      });
    }

    return beads;
  }

  /**
   * Convert magnet anomalies into alert beads
   */
  anomaliesToBeads(mission_id: string, magnetReports: MagnetReport[]): Bead[] {
    const beads: Bead[] = [];

    for (const report of magnetReports) {
      for (const anomaly of report.anomalies) {
        const priorityMap = { error: 0, warn: 2, info: 4 };

        beads.push({
          id: `alert-${mission_id}-${report.magnet_type}-${Date.now()}`,
          type: 'alert',
          status: 'pending',
          title: `[${report.magnet_type}] ${anomaly.message}`,
          description: anomaly.suggested_action,
          context: {
            magnet: report.magnet_type,
            level: anomaly.level,
            evidence: anomaly.evidence,
          },
          tags: [report.magnet_type, anomaly.level],
          priority: priorityMap[anomaly.level as keyof typeof priorityMap],
          source: {
            runtime: 'roach-pi',
            mission_id,
            stage: 'validation',
          },
          created_at: Date.now(),
        });
      }
    }

    return beads;
  }

  /**
   * Convert execution learnings into memory beads
   */
  learningsToBeads(mission_id: string, learnings: Learning[]): Bead[] {
    const beads: Bead[] = [];

    for (const learning of learnings) {
      beads.push({
        id: `learning-${mission_id}-${Date.now()}`,
        type: 'learning',
        status: 'completed',
        title: learning.title,
        description: learning.detail,
        context: {
          applicable_to: learning.applicable_to,
          confidence: learning.confidence,
        },
        tags: learning.tags,
        priority: 3, // Lower priority for learnings (informational)
        source: {
          runtime: 'roach-pi',
          mission_id,
          stage: 'synthesis',
        },
        evidence: { confidence: learning.confidence },
        created_at: Date.now(),
      });
    }

    return beads;
  }

  /**
   * Create a confidence score bead (for future missions)
   */
  scoreBeads(mission_id: string, execution: ExecutionResult, synthesis: any): Bead[] {
    const beads: Bead[] = [];

    if (synthesis.overall_confidence !== undefined) {
      beads.push({
        id: `score-${mission_id}-confidence`,
        type: 'score',
        status: 'completed',
        title: 'Mission Confidence Score',
        context: {
          overall: synthesis.overall_confidence,
          execution: synthesis.execution_quality,
          cost: synthesis.cost_efficiency,
          tests: synthesis.test_confidence,
        },
        tags: ['confidence', 'scoring', 'mission-complete'],
        priority: 4,
        source: {
          runtime: 'roach-pi',
          mission_id,
          stage: 'synthesis',
        },
        evidence: {
          synthesis,
          tokens_used: execution.telemetry.tokens_used,
          tests_passed: execution.telemetry.test_results?.length || 0,
        },
        created_at: Date.now(),
      });
    }

    return beads;
  }

  /**
   * Convert full execution result into all relevant beads
   */
  resultToBeads(result: ExecutionResult, synthesis: any): Bead[] {
    const allBeads: Bead[] = [];

    // Action beads (completed and follow-up work)
    allBeads.push(...this.executionToBeads(result));

    // Alert beads (magnet anomalies)
    allBeads.push(...this.anomaliesToBeads(result.mission_id, result.magnet_reports));

    // Learning beads (insights from execution)
    allBeads.push(...this.learningsToBeads(result.mission_id, result.learnings));

    // Score beads (confidence tracking)
    allBeads.push(...this.scoreBeads(result.mission_id, result, synthesis));

    return allBeads;
  }

  /**
   * Format beads for display
   */
  formatBeads(beads: Bead[]): string {
    const lines: string[] = [];

    // Group by type
    const byType: Record<string, Bead[]> = {};
    for (const bead of beads) {
      if (!byType[bead.type]) byType[bead.type] = [];
      byType[bead.type].push(bead);
    }

    lines.push('═══════════════════════════════════════');
    lines.push(`BEADS (${beads.length} total)`);
    lines.push('═══════════════════════════════════════');
    lines.push('');

    const typeOrder = ['alert', 'action', 'learning', 'score'];
    for (const type of typeOrder) {
      if (byType[type]) {
        lines.push(`[${type.toUpperCase()}]`);
        for (const bead of byType[type]) {
          const statusIcon =
            bead.status === 'completed'
              ? '✓'
              : bead.status === 'waiting'
                ? '⏸'
                : bead.status === 'pending'
                  ? '○'
                  : '→';
          lines.push(`  ${statusIcon} ${bead.title}`);
          if (bead.description) {
            lines.push(`     ${bead.description}`);
          }
        }
        lines.push('');
      }
    }

    lines.push('═══════════════════════════════════════');

    return lines.join('\n');
  }
}
