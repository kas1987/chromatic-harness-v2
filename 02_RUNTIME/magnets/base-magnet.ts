/**
 * Base Magnet Class
 *
 * All Magnets extend this to observe execution inflection points,
 * collect telemetry, detect anomalies, and score confidence.
 */

import { MagnetReport, Anomaly } from '../../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';

export abstract class BaseMagnet {
  readonly magnet_type: 'execution' | 'cost' | 'confidence' | 'validation' | 'security' | 'memory';
  protected observations: Record<string, any> = {};
  protected anomalies: Anomaly[] = [];
  protected startTime: number = Date.now();

  constructor(magnet_type: 'execution' | 'cost' | 'confidence' | 'validation' | 'security' | 'memory') {
    this.magnet_type = magnet_type;
  }

  /**
   * Record an observation
   */
  protected observe(key: string, value: any): void {
    this.observations[key] = value;
  }

  /**
   * Detect and record an anomaly
   */
  protected raiseAnomaly(level: 'info' | 'warn' | 'error', message: string, evidence: Record<string, any>, suggestedAction?: string): void {
    this.anomalies.push({
      level,
      message,
      evidence,
      suggested_action: suggestedAction,
    });
  }

  /**
   * Calculate confidence score (0-1)
   * Override in subclasses for custom scoring
   */
  protected calculateScore(): number {
    // Default: deduct points for anomalies
    let score = 1.0;
    for (const anomaly of this.anomalies) {
      if (anomaly.level === 'error') score -= 0.3;
      else if (anomaly.level === 'warn') score -= 0.1;
    }
    return Math.max(0, Math.min(1, score));
  }

  /**
   * Generate final magnet report
   */
  report(): MagnetReport {
    return {
      magnet_type: this.magnet_type,
      observations: this.observations,
      anomalies: this.anomalies,
      score: this.calculateScore(),
      timestamp: Date.now(),
    };
  }

  /**
   * Reset state for next mission
   */
  reset(): void {
    this.observations = {};
    this.anomalies = [];
    this.startTime = Date.now();
  }
}
