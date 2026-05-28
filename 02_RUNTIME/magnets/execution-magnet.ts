/**
 * Execution Magnet
 *
 * Observes what the runtime actually does:
 * - Tool calls (what, when, duration, success/failure)
 * - Errors (recoverable vs. unrecoverable)
 * - Retries (retry storms indicate problems)
 * - Tool call patterns (suspicious sequences)
 */

import { BaseMagnet } from './base-magnet';
import { ToolCall, ExecutionError } from '../../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';

export class ExecutionMagnet extends BaseMagnet {
  private toolCalls: ToolCall[] = [];
  private errors: ExecutionError[] = [];
  private retryStormThreshold = 3; // Flag if >3 retries of same tool in <5s
  private lastToolTimestamp = 0;

  constructor() {
    super('execution');
  }

  /**
   * Record a tool invocation
   */
  onToolCall(toolCall: ToolCall): void {
    this.toolCalls.push(toolCall);

    // Detect retry storms
    const recentRetries = this.toolCalls
      .slice(-10)
      .filter((tc) => tc.tool_name === toolCall.tool_name && tc.retry_count > 0);

    if (recentRetries.length >= this.retryStormThreshold) {
      const timeDiff = toolCall.timestamp - this.lastToolTimestamp;
      if (timeDiff < 5000) {
        // 5 seconds
        this.raiseAnomaly(
          'warn',
          `Retry storm detected: ${toolCall.tool_name} retried ${recentRetries.length} times in ${timeDiff}ms`,
          {
            tool: toolCall.tool_name,
            retry_count: recentRetries.length,
            time_window_ms: timeDiff,
          },
          'Check tool parameters or rate limits'
        );
      }
    }

    this.lastToolTimestamp = toolCall.timestamp;

    // Detect suspicious tool sequences
    if (this.toolCalls.length > 1) {
      const prev = this.toolCalls[this.toolCalls.length - 2];
      this.detectSuspiciousSequence(prev, toolCall);
    }

    this.observe('total_tool_calls', this.toolCalls.length);
    this.observe('tools_used', [...new Set(this.toolCalls.map((tc) => tc.tool_name))]);
    this.observe('avg_tool_duration_ms', this.calculateAvgToolDuration());
  }

  /**
   * Record an error
   */
  onError(error: ExecutionError): void {
    this.errors.push(error);

    if (!error.recoverable) {
      this.raiseAnomaly(
        'error',
        `Unrecoverable error in ${error.stage}: ${error.message}`,
        {
          stage: error.stage,
          code: error.code,
          recoverable: error.recoverable,
        },
        'Escalate to human review'
      );
    }

    // Warn on too many errors
    if (this.errors.length > 5) {
      this.raiseAnomaly(
        'warn',
        `High error rate: ${this.errors.length} errors in this execution`,
        { error_count: this.errors.length },
        'Review error logs for patterns'
      );
    }

    this.observe('total_errors', this.errors.length);
    this.observe('error_stages', [...new Set(this.errors.map((e) => e.stage))]);
  }

  /**
   * Detect suspicious tool call patterns
   * Examples: Accessing secrets, excessive file reads, injection attempts
   */
  private detectSuspiciousSequence(prev: ToolCall, current: ToolCall): void {
    // Flag: file_read immediately followed by file_write to same path (potential overwrite without verification)
    if (prev.tool_name === 'file_read' && current.tool_name === 'file_write') {
      if (prev.arguments.path === current.arguments.path) {
        this.raiseAnomaly(
          'info',
          `Direct overwrite: Read then Write to same path without verification`,
          {
            path: prev.arguments.path,
            tool_sequence: ['file_read', 'file_write'],
          }
        );
      }
    }

    // Flag: Environment variable access (potential secret exposure)
    if (current.tool_name === 'shell_exec' && current.arguments.command?.includes('$')) {
      this.raiseAnomaly(
        'warn',
        `Shell command with environment variable substitution detected`,
        {
          command: current.arguments.command.substring(0, 50), // Truncate for safety
          tool: 'shell_exec',
        },
        'Verify no secrets are exposed'
      );
    }

    // Flag: Rapid successive API calls (rate limit risk)
    if (current.tool_name === 'api_call' && prev.tool_name === 'api_call') {
      const timeDiff = current.timestamp - prev.timestamp;
      if (timeDiff < 100) {
        this.raiseAnomaly(
          'info',
          `Rapid API calls: ${timeDiff}ms apart`,
          { time_diff_ms: timeDiff },
          'Consider adding rate limit awareness'
        );
      }
    }
  }

  /**
   * Calculate average tool execution time
   */
  private calculateAvgToolDuration(): number {
    if (this.toolCalls.length === 0) return 0;
    const total = this.toolCalls.reduce((sum, tc) => sum + tc.duration_ms, 0);
    return Math.round(total / this.toolCalls.length);
  }

  /**
   * Custom score: high if few errors and retries
   */
  protected calculateScore(): number {
    let score = 1.0;

    // Penalize errors
    score -= this.errors.length * 0.05;

    // Penalize retries
    const totalRetries = this.toolCalls.reduce((sum, tc) => sum + tc.retry_count, 0);
    score -= totalRetries * 0.02;

    // Penalize anomalies
    for (const anomaly of this.anomalies) {
      if (anomaly.level === 'error') score -= 0.2;
      else if (anomaly.level === 'warn') score -= 0.05;
    }

    return Math.max(0, Math.min(1, score));
  }

  /**
   * Get raw tool calls for inspection
   */
  getToolCalls(): ToolCall[] {
    return [...this.toolCalls];
  }

  /**
   * Get raw errors for inspection
   */
  getErrors(): ExecutionError[] {
    return [...this.errors];
  }

  reset(): void {
    super.reset();
    this.toolCalls = [];
    this.errors = [];
  }
}
