import type { LlmProvider, ClaudeModelTier } from "../llm/llm-types.js";
import type { DelegationFailureReason } from "./delegation-log.js";

/**
 * When to trigger a fallback.
 *
 * Severity tiers:
 *   IMMEDIATE  — trigger on first failure, no retry
 *   AFTER_RETRY — allow N retries before falling back
 *   ADVISORY   — log but don't fall back; continue with degraded result
 */
export type FallbackSeverity = "immediate" | "after_retry" | "advisory";

export interface FallbackRule {
  trigger: DelegationFailureReason;
  severity: FallbackSeverity;
  maxRetries?: number;    // for "after_retry" severity
  note: string;           // logged to delegation_log.fallback_note
}

/**
 * Default fallback rules.
 *
 * Philosophy: fail fast on hard errors (unavailable, provider_error),
 * allow one retry on soft errors (timeout, low_confidence), never mask
 * empty responses.
 */
export const DEFAULT_FALLBACK_RULES: FallbackRule[] = [
  { trigger: "unavailable",     severity: "immediate",   note: "Provider unreachable — falling back to Sonnet immediately" },
  { trigger: "provider_error",  severity: "immediate",   note: "Provider threw an error — falling back to Sonnet immediately" },
  { trigger: "empty_response",  severity: "immediate",   note: "Provider returned empty response — falling back to Sonnet" },
  { trigger: "schema_invalid",  severity: "after_retry", maxRetries: 1, note: "Response schema invalid — retrying once, then Sonnet fallback" },
  { trigger: "timeout",         severity: "after_retry", maxRetries: 1, note: "Timeout — retrying once with shorter budget, then Sonnet fallback" },
  { trigger: "low_confidence",  severity: "after_retry", maxRetries: 1, note: "Low confidence — retrying once, then Sonnet fallback" },
  { trigger: "retry_exhausted", severity: "immediate",   note: "Retry budget exhausted — falling back to Sonnet" },
];

/**
 * The canonical fallback target.
 * Always Claude Sonnet — available via Max plan, no API key needed,
 * highest code quality within the auto-select tier.
 *
 * If the session budget for Sonnet is exhausted, the fallback chain
 * degrades to Haiku (still Max plan, 7-day budget only).
 */
export const FALLBACK_PROVIDER: LlmProvider = "claude";
export const FALLBACK_TIER: ClaudeModelTier = "sonnet";
export const FALLBACK_TIER_DEGRADED: ClaudeModelTier = "haiku"; // if sonnet session-exhausted

/**
 * Decides whether to fall back given the current failure reason and
 * how many attempts have already been made.
 */
export class FallbackPolicy {
  private rules: Map<DelegationFailureReason, FallbackRule>;

  constructor(rules: FallbackRule[] = DEFAULT_FALLBACK_RULES) {
    this.rules = new Map(rules.map((r) => [r.trigger, r]));
  }

  /**
   * Returns true if a fallback should be triggered now.
   *
   * @param reason  Why the delegation failed
   * @param attempt 1-based attempt count (attempt=1 = first try)
   */
  shouldFallback(reason: DelegationFailureReason, attempt: number): boolean {
    const rule = this.rules.get(reason);
    if (!rule) return true; // unknown failure → always fall back

    switch (rule.severity) {
      case "immediate":
        return true;
      case "after_retry":
        return attempt > (rule.maxRetries ?? 1);
      case "advisory":
        return false;
    }
  }

  /** Returns the note to log when falling back for this reason. */
  fallbackNote(reason: DelegationFailureReason): string {
    return this.rules.get(reason)?.note ?? `Unhandled failure reason '${reason}' — falling back to Sonnet`;
  }

  /**
   * Validates a response string against basic quality heuristics.
   * Returns the failure reason if invalid, null if acceptable.
   *
   * This is a lightweight first-pass check — not a schema validator.
   * Use expectedOutputFormat for richer validation downstream.
   */
  validateResponse(response: string | null | undefined): DelegationFailureReason | null {
    if (response == null || response.trim() === "") return "empty_response";
    // Truncated/incomplete responses
    if (response.length < 10) return "empty_response";
    return null;
  }
}
