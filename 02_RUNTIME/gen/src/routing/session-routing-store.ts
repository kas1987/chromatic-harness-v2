import type { IntentClass, ScopeLevel } from "../prompting/prompt-normalizer.js";
import type { LlmProvider } from "../llm/llm-types.js";

const TTL_MS = 5 * 60 * 1000; // 5 minutes

export interface RoutingHint {
  provider: LlmProvider;
  intent: IntentClass;
  scope: ScopeLevel;
  expiresAt: number;
  setAt: number;
}

class SessionRoutingStore {
  private store = new Map<string, RoutingHint>();
  private evictionsTotal = 0;

  set(sessionId: string, provider: LlmProvider, intent: IntentClass, scope: ScopeLevel): void {
    const now = Date.now();
    for (const [key, hint] of this.store) {
      if (hint.expiresAt <= now) {
        this.store.delete(key);
        this.evictionsTotal += 1;
      }
    }

    this.store.set(sessionId, {
      provider,
      intent,
      scope,
      setAt: now,
      expiresAt: now + TTL_MS,
    });
  }

  get(sessionId: string): RoutingHint | null {
    const hint = this.store.get(sessionId);
    if (!hint) return null;
    if (hint.expiresAt <= Date.now()) {
      this.store.delete(sessionId);
      this.evictionsTotal += 1;
      return null;
    }
    return hint;
  }

  /** Age bucket for OTel when session_intent routing applies; null if no valid hint. */
  getHintAgeBucket(sessionId: string): string | null {
    const hint = this.store.get(sessionId);
    if (!hint || hint.expiresAt <= Date.now()) return null;
    const ageMs = Date.now() - hint.setAt;
    if (ageMs < 30_000) return "0-30s";
    if (ageMs < 120_000) return "30s-2m";
    return "2m-5m";
  }

  getStats(): { size: number; evictionsTotal: number } {
    return { size: this.store.size, evictionsTotal: this.evictionsTotal };
  }
}

export const sessionRoutingStore = new SessionRoutingStore();
