/**
 * Cost Magnet
 *
 * Tracks resource consumption:
 * - Token usage (vs. budget)
 * - Tool call count (vs. budget)
 * - Wall-clock time (vs. budget)
 * - Cost per task (useful for optimization)
 */

import { BaseMagnet } from './base-magnet';

export interface CostBudget {
  tokens: number;
  tool_calls: number;
  wall_time_seconds?: number;
}

export class CostMagnet extends BaseMagnet {
  private budget: CostBudget;
  private tokensUsed = 0;
  private toolCallsCount = 0;

  constructor(budget: CostBudget) {
    super('cost');
    this.budget = budget;
    this.observe('budget', budget);
  }

  /**
   * Record tokens consumed
   */
  onTokensUsed(count: number): void {
    this.tokensUsed += count;

    // Check if over budget
    if (this.tokensUsed > this.budget.tokens) {
      this.raiseAnomaly(
        'error',
        `Token budget exceeded: ${this.tokensUsed} / ${this.budget.tokens}`,
        {
          tokens_used: this.tokensUsed,
          budget: this.budget.tokens,
          overflow: this.tokensUsed - this.budget.tokens,
        },
        'Escalate to human review or increase budget'
      );
    } else if (this.tokensUsed > this.budget.tokens * 0.8) {
      this.raiseAnomaly(
        'warn',
        `Token budget 80% consumed: ${this.tokensUsed} / ${this.budget.tokens}`,
        {
          tokens_used: this.tokensUsed,
          budget: this.budget.tokens,
          percent_remaining: Math.round(((this.budget.tokens - this.tokensUsed) / this.budget.tokens) * 100),
        },
        'Consider wrapping up or requesting more budget'
      );
    }

    this.observe('tokens_used', this.tokensUsed);
    this.observe('tokens_remaining', Math.max(0, this.budget.tokens - this.tokensUsed));
  }

  /**
   * Record tool invocation (counts toward tool_calls budget)
   */
  onToolInvocation(): void {
    this.toolCallsCount++;

    // Check if over budget
    if (this.toolCallsCount > this.budget.tool_calls) {
      this.raiseAnomaly(
        'error',
        `Tool call budget exceeded: ${this.toolCallsCount} / ${this.budget.tool_calls}`,
        {
          tool_calls: this.toolCallsCount,
          budget: this.budget.tool_calls,
          overflow: this.toolCallsCount - this.budget.tool_calls,
        },
        'Escalate to human review or increase budget'
      );
    } else if (this.toolCallsCount > this.budget.tool_calls * 0.8) {
      this.raiseAnomaly(
        'warn',
        `Tool call budget 80% consumed: ${this.toolCallsCount} / ${this.budget.tool_calls}`,
        {
          tool_calls: this.toolCallsCount,
          budget: this.budget.tool_calls,
          percent_remaining: Math.round(((this.budget.tool_calls - this.toolCallsCount) / this.budget.tool_calls) * 100),
        },
        'Consider wrapping up or requesting more tool calls'
      );
    }

    this.observe('tool_calls', this.toolCallsCount);
    this.observe('tool_calls_remaining', Math.max(0, this.budget.tool_calls - this.toolCallsCount));
  }

  /**
   * Get wall-clock time used
   */
  getWallTimeSeconds(): number {
    return (Date.now() - this.startTime) / 1000;
  }

  /**
   * Check wall time budget (if configured)
   */
  checkWallTimeBudget(): void {
    if (!this.budget.wall_time_seconds) return;

    const elapsed = this.getWallTimeSeconds();

    if (elapsed > this.budget.wall_time_seconds) {
      this.raiseAnomaly(
        'error',
        `Wall time budget exceeded: ${elapsed.toFixed(1)}s / ${this.budget.wall_time_seconds}s`,
        {
          elapsed_seconds: elapsed,
          budget_seconds: this.budget.wall_time_seconds,
          overflow_seconds: elapsed - this.budget.wall_time_seconds,
        },
        'Timeout: escalate or increase wall time'
      );
    } else if (elapsed > this.budget.wall_time_seconds * 0.8) {
      this.raiseAnomaly(
        'warn',
        `Wall time budget 80% consumed: ${elapsed.toFixed(1)}s / ${this.budget.wall_time_seconds}s`,
        {
          elapsed_seconds: elapsed,
          budget_seconds: this.budget.wall_time_seconds,
          percent_remaining: Math.round(((this.budget.wall_time_seconds - elapsed) / this.budget.wall_time_seconds) * 100),
        }
      );
    }

    this.observe('wall_time_seconds', elapsed);
    this.observe('wall_time_remaining', Math.max(0, this.budget.wall_time_seconds - elapsed));
  }

  /**
   * Calculate efficiency (how much work per token/call)
   */
  getEfficiency(): {
    tokens_per_task: number;
    tool_calls_per_task: number;
    seconds_per_task: number;
  } {
    return {
      tokens_per_task: Math.round(this.tokensUsed / Math.max(1, this.toolCallsCount)),
      tool_calls_per_task: this.toolCallsCount,
      seconds_per_task: this.getWallTimeSeconds(),
    };
  }

  /**
   * Custom score: high if under budget
   */
  protected calculateScore(): number {
    let score = 1.0;

    // Penalize token overage
    if (this.tokensUsed > this.budget.tokens) {
      const overflow = this.tokensUsed - this.budget.tokens;
      score -= Math.min(0.3, (overflow / this.budget.tokens) * 0.5);
    }

    // Penalize tool call overage
    if (this.toolCallsCount > this.budget.tool_calls) {
      const overflow = this.toolCallsCount - this.budget.tool_calls;
      score -= Math.min(0.3, (overflow / this.budget.tool_calls) * 0.5);
    }

    // Penalize anomalies
    for (const anomaly of this.anomalies) {
      if (anomaly.level === 'error') score -= 0.2;
      else if (anomaly.level === 'warn') score -= 0.05;
    }

    return Math.max(0, Math.min(1, score));
  }

  reset(): void {
    super.reset();
    this.tokensUsed = 0;
    this.toolCallsCount = 0;
    this.startTime = Date.now();
  }
}
