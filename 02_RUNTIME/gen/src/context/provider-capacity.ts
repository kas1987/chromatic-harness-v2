/**
 * Provider capacity tracking — load awareness beyond simple reachability.
 *
 * isAvailable() tells you the server is up. This module tells you whether
 * the server can take NEW work RIGHT NOW without degrading active pipelines.
 *
 * Per-provider concerns:
 *   ollama    — single model loaded at a time; if a vision model is running
 *               image tagging, routing code tasks means a model swap (20-60s
 *               VRAM churn) or a queue pile-up behind the active generation
 *   lm-studio — same single-model constraint; only one GGUF loaded at a time
 *   gemini    — free tier: 15 req/min. More than 3 concurrent delegations
 *               triggers 429s and cascades into unnecessary fallbacks
 *   gpt       — rate-limited; concurrent requests consume budget faster
 *   claude    — session budget (5h Sonnet window); concurrent calls drain it
 */

import type { LlmProvider } from "../llm/llm-types.js";

export interface SlotState {
  inFlight: number;
  maxSlots: number;
  atCapacity: boolean;
}

export interface OllamaRunningModel {
  name: string;
  /** VRAM used by this model in bytes. */
  size: number;
  /** Digest hash (unused here, for reference). */
  digest?: string;
}

/**
 * Max concurrent in-flight delegation requests per provider.
 *
 * These are conservative — they prevent cascading overload, not just
 * individual provider rate limits.
 *
 *   ollama/lm-studio → 1: single model, no parallel inference
 *   gemini           → 3: 15 RPM ÷ ~5s avg = ~3 safe concurrent
 *   gpt              → 5: rate limited but can handle moderate concurrency
 *   claude           → 8: Max plan handles concurrency; session-budget-aware
 */
const MAX_SLOTS: Record<LlmProvider, number> = {
  ollama:       1,
  gemma:        1,   // same Ollama server as ollama — one in-flight local inference slot
  "lm-studio":  1,
  minimax:      2,   // cloud MoE — moderate concurrency, rate-limited
  gemini:       3,
  gpt:          5,
  claude:       8,
};

export class ProviderCapacityTracker {
  private inFlight = new Map<LlmProvider, number>();

  /**
   * Try to acquire a delegation slot for the given provider.
   * Returns true if acquired (caller must call release() when done).
   * Returns false if provider is at capacity — caller should skip to next.
   */
  acquire(provider: LlmProvider): boolean {
    const current = this.inFlight.get(provider) ?? 0;
    const max = MAX_SLOTS[provider];
    if (current >= max) return false;
    this.inFlight.set(provider, current + 1);
    return true;
  }

  release(provider: LlmProvider): void {
    const current = this.inFlight.get(provider) ?? 0;
    this.inFlight.set(provider, Math.max(0, current - 1));
  }

  isAtCapacity(provider: LlmProvider): boolean {
    return (this.inFlight.get(provider) ?? 0) >= MAX_SLOTS[provider];
  }

  getSnapshot(): Record<LlmProvider, SlotState> {
    const providers: LlmProvider[] = ["claude", "gemini", "gpt", "minimax", "lm-studio", "ollama", "gemma"];
    return Object.fromEntries(
      providers.map((p) => {
        const inFlight = this.inFlight.get(p) ?? 0;
        return [p, { inFlight, maxSlots: MAX_SLOTS[p], atCapacity: inFlight >= MAX_SLOTS[p] }];
      })
    ) as Record<LlmProvider, SlotState>;
  }
}

/**
 * Queries Ollama's /api/ps to see which models are currently loaded/running.
 *
 * This is the key check for avoiding model-swap penalties:
 *   - If the model we want IS the one loaded → route normally (no swap)
 *   - If a DIFFERENT model is loaded AND it's actively running → skip Ollama
 *     (routing would either queue behind active generation or trigger a swap)
 *   - If nothing is loaded → Ollama is idle, safe to use
 *
 * /api/ps example response:
 *   { "models": [{ "name": "qwen3-vl:4b", "size": 5e9, ... }] }
 *   empty models array means no active model
 */
export async function getOllamaRunningModels(ollamaUrl: string): Promise<OllamaRunningModel[]> {
  try {
    const resp = await fetch(`${ollamaUrl}/api/ps`, {
      signal: AbortSignal.timeout(2000),
    });
    if (!resp.ok) return [];
    const data = await resp.json() as { models?: OllamaRunningModel[] };
    return data.models ?? [];
  } catch {
    return [];
  }
}

/**
 * Decide whether Ollama can safely take the requested model right now.
 *
 * Returns:
 *   "ready"      — requested model is already loaded, no swap needed
 *   "idle"       — no model loaded, safe to load and use
 *   "swap"       — different model loaded, using it costs a model swap (20-60s)
 *   "busy"       — same as swap but the loaded model is known to be large (vision/14B+)
 */
export type OllamaReadiness = "ready" | "idle" | "swap" | "busy";

const LARGE_MODEL_PATTERNS = ["-vl", "vision", "14b", "32b", "70b", "nsfw-tagger"];

export async function checkOllamaReadiness(
  ollamaUrl: string,
  requestedModel: string,
): Promise<OllamaReadiness> {
  const running = await getOllamaRunningModels(ollamaUrl);

  if (running.length === 0) return "idle";

  const loadedName = running[0].name.toLowerCase();
  const requested = requestedModel.toLowerCase();

  // Exact match or same base model — no swap needed
  if (loadedName === requested || loadedName.startsWith(requested.split(":")[0])) {
    return "ready";
  }

  // Different model is loaded. Is it large/vision (expensive to evict)?
  const isLarge = LARGE_MODEL_PATTERNS.some((pat) => loadedName.includes(pat));
  return isLarge ? "busy" : "swap";
}
