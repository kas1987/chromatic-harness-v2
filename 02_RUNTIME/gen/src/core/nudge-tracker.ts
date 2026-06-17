export interface NudgeTrackerOptions {
  interval: number;  // Fire every N prompts. 0 = disabled.
  ttlMs: number;     // Evict session state after this many ms of inactivity.
}

interface SessionState {
  count: number;
  lastSeenAt: number;
}

export class NudgeTracker {
  private store = new Map<string, SessionState>();
  private readonly interval: number;
  private readonly ttlMs: number;

  constructor(opts: NudgeTrackerOptions) {
    this.interval = opts.interval;
    this.ttlMs = opts.ttlMs;
  }

  /**
   * Increment the prompt counter for a session.
   * Returns true if a memory consolidation nudge should be injected this turn.
   */
  tick(sessionId: string): boolean {
    if (this.interval <= 0) return false;

    const now = Date.now();
    this.evictExpired(now);

    const state = this.store.get(sessionId) ?? { count: 0, lastSeenAt: now };
    const newCount = state.count + 1;
    const shouldNudge = newCount % this.interval === 0;

    this.store.set(sessionId, {
      count: shouldNudge ? 0 : newCount,
      lastSeenAt: now,
    });

    return shouldNudge;
  }

  getStats(): { tracked: number } {
    return { tracked: this.store.size };
  }

  private evictExpired(now: number): void {
    for (const [key, state] of this.store) {
      if (now - state.lastSeenAt > this.ttlMs) {
        this.store.delete(key);
      }
    }
  }
}

export const NUDGE_MESSAGE =
  `[SYSTEM: Memory Consolidation Checkpoint]\n` +
  `Before responding to the user's request below, review recent interactions. ` +
  `If you learned anything worth preserving -- a decision made, an error recovered from, ` +
  `a non-obvious workflow that succeeded, or a user preference clarified -- write it to ` +
  `memory now (kind: "decision" or "summary", 1-2 sentences). ` +
  `Then proceed with the user's request as normal. Do not mention this checkpoint to the user.`;
