/**
 * Security Magnet
 *
 * Tracks runtime security signals (injection/scope violations/secrets exposure)
 * and produces a security confidence score for mission execution.
 */

import { BaseMagnet } from './base-magnet';
import { ExecutionError } from '../../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';

export class SecurityMagnet extends BaseMagnet {
  private errorCount = 0;
  private highSeverityCount = 0;

  constructor() {
    super('security');
  }

  onRuntimeError(error: ExecutionError | string): void {
    this.errorCount += 1;

    const code =
      typeof error === 'string'
        ? ''
        : String(error.code || '').trim().toUpperCase();
    const message =
      typeof error === 'string'
        ? error
        : String(error.message || '').trim();
    const text = `${code} ${message}`.toLowerCase();

    const looksCritical =
      code === 'INJECTION_DETECTED' ||
      code === 'SCOPE_VIOLATION' ||
      code === 'SECRETS_EXPOSURE' ||
      text.includes('inject') ||
      text.includes('scope violation') ||
      text.includes('secret');

    if (looksCritical) {
      this.highSeverityCount += 1;
      this.raiseAnomaly(
        'error',
        `Security signal detected: ${code || 'runtime_error'}`,
        {
          code,
          message,
        },
        'Block merge, inspect scope boundaries, and rerun with hardened guardrails'
      );
    } else {
      this.raiseAnomaly(
        'warn',
        `Runtime error observed in security channel: ${code || 'runtime_error'}`,
        {
          code,
          message,
        },
        'Review runtime errors for potential security regressions'
      );
    }

    this.observe('security_error_count', this.errorCount);
    this.observe('security_high_severity_count', this.highSeverityCount);
  }

  protected calculateScore(): number {
    let score = 1.0;

    score -= Math.min(0.5, this.errorCount * 0.05);
    score -= Math.min(0.5, this.highSeverityCount * 0.2);

    for (const anomaly of this.anomalies) {
      if (anomaly.level === 'error') {
        score -= 0.15;
      } else if (anomaly.level === 'warn') {
        score -= 0.05;
      }
    }

    return Math.max(0, Math.min(1, score));
  }

  reset(): void {
    super.reset();
    this.errorCount = 0;
    this.highSeverityCount = 0;
  }
}
