import { LlmProvider, LlmTask, ILlmClient, ClaudeModelTier, CLAUDE_TIER_FOR_SCOPE } from "./llm-types.js";
import { createClient } from "./llm-client-factory.js";
import { config } from "../config.js";
import type { IntentClass } from "../prompting/prompt-normalizer.js";

/**
 * Maps an intent class to LLM routing hints.
 * Routine/read-only intents route to Ollama; code/dispatch intents route to Claude.
 */
export function intentToRoutingHints(intent: IntentClass): { requiresLocal: boolean; requiresCode: boolean } {
  switch (intent) {
    case "explore":
    case "status":
    case "manage":
    case "trigger":
    case "schedule":
      return { requiresLocal: true, requiresCode: false };
    case "code":
    case "dispatch":
      return { requiresLocal: false, requiresCode: true };
    default: {
      // Exhaustive check — TypeScript will error if a new IntentClass is added without handling it
      const _exhaustive: never = intent;
      void _exhaustive;
      return { requiresLocal: false, requiresCode: true };
    }
  }
}

const VALID_PROVIDERS = new Set<string>(["claude", "gpt", "gemini", "ollama", "lm-studio", "minimax", "gemma"]);
// Fallback order: claude (Max plan, free) → gpt → gemini → minimax (large-context cloud) → lm-studio (local heavy) → ollama / gemma (local)
const FALLBACK_CHAIN: LlmProvider[] = ["claude", "gpt", "gemini", "minimax", "lm-studio", "ollama", "gemma"];

/**
 * Validates a raw string against the known LlmProvider set.
 * Unknown values return "claude" (safe default).
 */
export function toProvider(raw: string): LlmProvider {
  return VALID_PROVIDERS.has(raw) ? (raw as LlmProvider) : "claude";
}

type TrackerLike = { getBestModel(intent: string, scope: string): LlmProvider | null } | null;

// Factory type accepts either the real factory (provider + config) or a test factory (provider only)
type ClientFactory = ((provider: LlmProvider, cfg: typeof config) => ILlmClient) | ((provider: LlmProvider) => ILlmClient);

export class LlmSelector {
  // Per-instance availability cache: provider → { value, expiresAt }
  private _availCache = new Map<LlmProvider, { v: boolean; exp: number }>();

  constructor(
    private clientFactory: ClientFactory = createClient,
    private performanceTracker: TrackerLike = null,
  ) {}

  /**
   * Synchronous, pure heuristic selector.
   * Rules evaluated in strict priority order (first match wins):
   *  1. requiresLocal                        → "ollama"
   *  2. requiresVision + nsfwContext          → "ollama" (abliterated model, no content refusals)
   *  3. requiresVision                       → "gemini"
   *  4. budgetConstraint="low" + tokens<10K  → "gpt"
   *  5. budgetConstraint="low" (large tokens) → "ollama"
   *  6. estimatedInputTokens > 50_000        → "minimax" (198K window)
   *  7. requiresCode OR intent="code"        → "claude"
   *  8. performanceTracker returns non-null   → learned model
   *  9. Default                              → "claude"
   */
  selectBestLlm(task: LlmTask): LlmProvider {
    if (task.requiresLocal) return "ollama";
    // NSFW vision: route to Ollama (uses qwen3-vl-abliterated) — Gemini refuses explicit content.
    if (task.requiresVision && task.nsfwContext) return "ollama";
    if (task.requiresVision) return "gemini";
    if (task.budgetConstraint === "low") {
      const tokens = task.estimatedInputTokens ?? Infinity;
      return tokens < 10_000 ? "gpt" : "ollama";
    }
    // Large-context tasks: MiniMax has 198K window vs Ollama's 32K limit.
    // requiresLocal=true already returned above, so this only fires for cloud-eligible tasks.
    if ((task.estimatedInputTokens ?? 0) > 50_000) return "minimax";
    if (task.requiresCode || task.intent === "code") return "claude";

    if (this.performanceTracker !== null) {
      const learned = this.performanceTracker.getBestModel(task.intent, task.scope);
      if (learned !== null) return learned;
    }

    return "claude";
  }

  /**
   * Returns the appropriate Claude model tier for a task.
   * - simple  → haiku  (7-day budget only, no session cap — safe to use freely)
   * - medium  → sonnet (5-hour session budget + 7-day — use intentionally)
   * - complex → sonnet (never auto-escalate to opus)
   *
   * Opus is NEVER returned by this method. Users must explicitly request it.
   * Task may override via claudeModelTier field.
   */
  selectClaudeTier(task: LlmTask): ClaudeModelTier {
    if (task.claudeModelTier) return task.claudeModelTier;
    return CLAUDE_TIER_FOR_SCOPE[task.scope];
  }

  /**
   * Async selector with availability probing and fallback chain.
   * Uses a per-instance 30s TTL cache to avoid redundant isAvailable() probes.
   * If ALL providers unavailable, returns "ollama" unconditionally.
   */
  async selectAvailableLlm(task: LlmTask): Promise<LlmProvider> {
    const preferred = this.selectBestLlm(task);

    // Build probe order: preferred first, then rest of fallback chain (skip preferred)
    const probeOrder: LlmProvider[] = [
      preferred,
      ...FALLBACK_CHAIN.filter((p) => p !== preferred),
    ];

    for (const provider of probeOrder) {
      const available = await this._cachedAvailable(provider);
      if (available) return provider;
    }

    return "ollama"; // Always available as local fallback
  }

  private async _cachedAvailable(provider: LlmProvider): Promise<boolean> {
    const hit = this._availCache.get(provider);
    if (hit && hit.exp > Date.now()) return hit.v;

    const client: ILlmClient = (this.clientFactory as (p: LlmProvider, cfg?: typeof config) => ILlmClient)(provider, config);
    const v = await client.isAvailable().catch(() => false);
    this._availCache.set(provider, { v, exp: Date.now() + 30_000 });
    return v;
  }
}
