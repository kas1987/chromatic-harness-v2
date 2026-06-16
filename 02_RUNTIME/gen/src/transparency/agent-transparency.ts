/**
 * Cross-agent transparency service.
 *
 * Surfaces shared state that prevents agents from operating in silos:
 *   - activeLlm: which provider is currently handling this session
 *   - routingConfidence: how certain the routing decision was [0–1]
 *   - activeTasks: what the agent is currently working on
 *   - upcomingWork: next-work.jsonl items not yet consumed
 *   - driftAlerts: cases where suggested LLM != actual LLM used
 *
 * Injected into hook responses as `gen.transparency_snapshot` so every
 * agent calling pretool/posttool hooks shares the same operational picture
 * before independently executing tasks.
 *
 * REST endpoint: GET /transparency/status (see transparency-route.ts)
 */

export interface TransparencySnapshot {
  /** ISO timestamp when snapshot was generated */
  generatedAt: string;
  /** Provider currently active for this session */
  activeLlm: string;
  /** Routing confidence score [0–1]. 1.0 = unambiguous, <0.5 = uncertain */
  routingConfidence: number;
  /** Active task labels surfaced from current session context */
  activeTasks: string[];
  /** Unconsumed high-priority next-work items (capped at 10 for hook injection size) */
  upcomingWork: Array<{ title: string; severity: string }>;
  /** Recent drift alerts: cases where suggested != actual LLM (last 5 for hook injection) */
  driftAlerts: DriftAlert[];
}

export interface DriftAlert {
  /** ISO timestamp of the divergence event */
  timestamp: string;
  /** Provider the routing logic recommended */
  suggested: string;
  /** Provider that actually handled the request */
  actual: string;
  /** IntentClass that was being processed */
  intent: string;
  /** Why the divergence happened (e.g., "suggested unavailable, fell back") */
  reason: string;
}

export class AgentTransparencyService {
  private readonly driftLog: DriftAlert[] = [];
  private readonly MAX_DRIFT_LOG = 20;

  /**
   * Record a divergence event when the actual LLM differs from what routing suggested.
   * Called from the posttool hook handler when gen.actual_llm !== gen.suggested_llm.
   */
  recordDrift(suggested: string, actual: string, intent: string, reason: string): void {
    this.driftLog.unshift({
      timestamp: new Date().toISOString(),
      suggested,
      actual,
      intent,
      reason,
    });
    // Cap log size to prevent unbounded memory growth
    if (this.driftLog.length > this.MAX_DRIFT_LOG) {
      this.driftLog.pop();
    }
  }

  /**
   * Build a snapshot of the current operational state.
   * upcomingWork is populated separately by the route handler (reads next-work.jsonl).
   */
  buildSnapshot(
    activeLlm: string,
    routingConfidence: number,
    activeTasks: string[] = [],
  ): TransparencySnapshot {
    return {
      generatedAt: new Date().toISOString(),
      activeLlm,
      routingConfidence,
      activeTasks,
      upcomingWork: [], // populated by transparency-route.ts readUpcomingWork()
      driftAlerts: this.driftLog.slice(0, 5), // cap at 5 for hook injection payload size
    };
  }

  /** Return a copy of the full drift log (up to MAX_DRIFT_LOG entries). */
  getRecentDrift(): DriftAlert[] {
    return [...this.driftLog];
  }

  /** Clear the drift log (e.g., after a session reset). */
  clearDrift(): void {
    this.driftLog.length = 0;
  }

  /** Drift rate: percentage of recent requests with LLM divergence (last 20 events). */
  getDriftRate(): number {
    if (this.driftLog.length === 0) return 0;
    return this.driftLog.length / this.MAX_DRIFT_LOG;
  }
}

/** Singleton instance shared across hook routes and the transparency endpoint. */
export const agentTransparencyService = new AgentTransparencyService();
