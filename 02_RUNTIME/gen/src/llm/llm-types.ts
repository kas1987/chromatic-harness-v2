/**
 * Routing targets for the multi-LLM orchestration layer.
 *
 * claude     — Claude Code Max plan (always available, $0 per token, session-budget-aware)
 * gpt        — OpenAI GPT via API key or ChatGPT Plus plan
 * gemini     — Google Gemini via API key or Gemini Advanced plan
 * ollama     — Local Ollama (lightweight models: qwen3:4b, mistral, etc.)
 * lm-studio  — LM Studio local server (heavy models: qwen2.5-coder:32b, etc.)
 *              OpenAI-compatible API at localhost:1234 — no key needed, all compute is local
 * minimax    — MiniMax-M2.5 (229B MoE, 198K context). Cloud-only via Ollama :cloud tag or
 *              direct MiniMax API. Local GGUF requires 101GB+ RAM — not viable on RTX 4070.
 *              Enable: GEN_ENABLE_MINIMAX=true + ollama pull minimax-m2.5:cloud
 * gemma      — Google Gemma on **local Ollama** (separate tag from GEN_OLLAMA_MODEL).
 *              Pull: `ollama pull gemma3:4b` (or your tag). Enable: GEN_ENABLE_GEMMA=true.
 */
export type LlmProvider = "claude" | "gpt" | "gemini" | "ollama" | "lm-studio" | "minimax" | "gemma";

/**
 * Claude model tiers available for auto-selection.
 * Opus is intentionally excluded — it is NEVER auto-selected; the user must
 * explicitly request it via task.claudeModelTier = "opus" (not typed here).
 */
export type ClaudeModelTier = "haiku" | "sonnet";

/**
 * Canonical model IDs for each Claude tier.
 *
 * Budget constraints under Claude Max plan:
 *  - haiku:  7-day rolling budget only (no per-session cap) — prefer for simple/quick tasks
 *  - sonnet: 5-hour session budget + 7-day rolling budget — use for medium/complex tasks
 *  - opus:   USER-DIRECTED ONLY — never auto-selected by routing logic
 */
export const CLAUDE_MODEL_IDS: Record<ClaudeModelTier, string> = {
  haiku:  "claude-haiku-4-5-20251001",
  sonnet: "claude-sonnet-4-6",
  // opus: "claude-opus-4-6" — available via explicit user request only
};

export const CLAUDE_MODEL_POLICY = {
  haiku:  { sessionBudget: false, weeklyBudget: true,  autoSelect: true,  note: "7-day budget only; no per-session cap" },
  sonnet: { sessionBudget: true,  weeklyBudget: true,  autoSelect: true,  note: "5-hour session budget + 7-day budget" },
  opus:   { sessionBudget: true,  weeklyBudget: true,  autoSelect: false, note: "user-directed only; never auto-selected" },
} as const;

/**
 * Task-to-tier routing recommendation.
 * Maps scope to the appropriate Claude model tier to respect session budgets.
 */
export const CLAUDE_TIER_FOR_SCOPE: Record<"simple" | "medium" | "complex", ClaudeModelTier> = {
  simple:  "haiku",   // no session budget constraint; use for reads, quick analysis
  medium:  "sonnet",  // session-budget-aware; use for code gen, planning
  complex: "sonnet",  // always sonnet for complex work (never auto-escalate to opus)
};

export interface LlmCapability {
  vision: boolean;
  functionCalling: boolean;
  maxInputTokens: number;
  /** Cost per 1k input tokens. Claude = 0 under Max plan (metered only when using raw API key). */
  costPer1kInputUsd: number;
  /** Cost per 1k output tokens. Claude = 0 under Max plan (metered only when using raw API key). */
  costPer1kOutputUsd: number;
  avgLatencyMs: number;
}

/**
 * Capability and cost profile per provider.
 *
 * Claude costs are 0.0 because we route through the Claude Code Max plan subscription,
 * not a raw API key. The Max plan has no per-token billing — costs are covered by the
 * flat subscription fee. GPT and Gemini are called via their plan-level API keys and
 * accrue metered cost; Ollama is free/local.
 *
 * Metered API rates (reference only, not used for routing decisions):
 *   claude-sonnet: $0.003/1k input, $0.015/1k output
 *   claude-haiku:  $0.00025/1k input, $0.00125/1k output
 */
export const LLM_CAPABILITIES: Record<LlmProvider, LlmCapability> = {
  claude:     { vision: true,  functionCalling: true,  maxInputTokens: 200_000,   costPer1kInputUsd: 0.0,     costPer1kOutputUsd: 0.0,    avgLatencyMs: 1200 },
  gpt:        { vision: true,  functionCalling: true,  maxInputTokens: 128_000,   costPer1kInputUsd: 0.00015, costPer1kOutputUsd: 0.0006, avgLatencyMs: 600  },
  gemini:     { vision: true,  functionCalling: true,  maxInputTokens: 1_000_000, costPer1kInputUsd: 0.0001,  costPer1kOutputUsd: 0.0004, avgLatencyMs: 800  },
  ollama:     { vision: false, functionCalling: false, maxInputTokens: 32_000,    costPer1kInputUsd: 0.0,     costPer1kOutputUsd: 0.0,    avgLatencyMs: 400  },
  // LM Studio: local server (OpenAI-compatible), zero cost, higher latency than Ollama due to heavier models
  "lm-studio": { vision: false, functionCalling: false, maxInputTokens: 128_000,  costPer1kInputUsd: 0.0,     costPer1kOutputUsd: 0.0,    avgLatencyMs: 2000 },
  // MiniMax: 229B MoE, cloud-only. Tool use supported (M2.5+). Latency higher than local models.
  // Pricing: MiniMax platform rates (metered). 0.0002/0.0006 per 1k in/out tokens (reference).
  minimax:    { vision: false, functionCalling: true,  maxInputTokens: 198_000,   costPer1kInputUsd: 0.0002,  costPer1kOutputUsd: 0.0006, avgLatencyMs: 2500 },
  // Gemma via Ollama — same VRAM / single-model constraints as generic ollama
  gemma:      { vision: false, functionCalling: false, maxInputTokens: 128_000,   costPer1kInputUsd: 0.0,     costPer1kOutputUsd: 0.0,    avgLatencyMs: 500  },
};

/**
 * Locally installed Ollama models (as of 2026-04-03).
 * Update when models are added/removed via `ollama list`.
 *
 * VRAM tiers based on RTX 4070 (12 GB):
 *   light  — safe even when ComfyUI is generating (≤5 GB)
 *   medium — safe when ComfyUI is idle (5–10 GB)
 *   heavy  — idle mode only, time-sliced with ComfyUI (>10 GB)
 */
export const OLLAMA_FLEET = {
  light:  ["qwen3:4b", "qwen3-vl:4b", "nsfw-tagger:latest", "gemma3:4b", "gemma3:1b"],
  medium: ["mistral:latest", "qwen2.5-coder:7b", "deepseek-r1:7b", "qwen3:8b", "qwen3-vl:8b", "llava:7b", "gemma4:e4b-it-q4_K_M", "gemma3:12b"],
  heavy:  ["phi4:latest", "qwen2.5-coder:14b", "qwen3:14b", "gpt-oss:20b"],
  /** Vision models with NSFW content restrictions removed (abliterated). */
  "vision-nsfw": ["huihui_ai/qwen3-vl-abliterated:4b-instruct"],
} as const;

/**
 * Default Ollama model for NSFW vision tasks (RAG image analysis, confidence scoring, tagger).
 * Standard qwen3-vl has content refusals on explicit material; this abliterated variant removes
 * those restrictions. Light tier (3.3 GB) — safe to run alongside ComfyUI.
 *
 * Install: ollama pull huihui_ai/qwen3-vl-abliterated:4b-instruct
 */
export const OLLAMA_NSFW_VISION_MODEL = "huihui_ai/qwen3-vl-abliterated:4b-instruct";

/**
 * Gemma 4 — 4B effective-param instruct model, Q4_K_M quantization, 9.6 GB.
 * Medium tier (RTX 4070 safe when ComfyUI idle).
 * Used by Hop middleware for fast local intent classification on dispatch routing.
 * Already installed: ollama pull gemma4:e4b-it-q4_K_M
 */
export const OLLAMA_DISPATCH_CLASSIFIER_MODEL = "gemma4:e4b-it-q4_K_M";

/**
 * Recommended Ollama model per VRAM session mode.
 * Matches the modes defined in gen/src/context/vram-guard.ts.
 */
export const OLLAMA_MODEL_FOR_MODE: Record<"heavy" | "light" | "idle", string> = {
  heavy: "qwen3:4b",       // ComfyUI actively generating — only light models safe
  light: "mistral:latest", // ComfyUI idle — medium models available
  idle:  "qwen2.5-coder:14b", // Full capacity — use best available coding model
};

export interface LlmTask {
  intent: string;
  scope: "simple" | "medium" | "complex";
  requiresVision?: boolean;
  requiresCode?: boolean;
  requiresLocal?: boolean;
  /** NSFW content context — routes vision tasks to abliterated models instead of Gemini. */
  nsfwContext?: boolean;
  budgetConstraint?: "low" | "medium" | "high";
  estimatedInputTokens?: number;
  maxOutputTokens?: number;
  /** Override Claude tier. Defaults to CLAUDE_TIER_FOR_SCOPE[scope]. "opus" only via user direction. */
  claudeModelTier?: ClaudeModelTier;
}

/** Options for `ILlmClient.generate` — extended by provider-specific fields. */
export interface LlmGenerateOptions {
  maxTokens?: number;
  temperature?: number;
  /**
   * Per-call Ollama model tag for `ollama` / `gemma` providers only.
   * When set, overrides `GEN_OLLAMA_MODEL` / `GEN_GEMMA_OLLAMA_MODEL` for that request.
   */
  localModelTag?: string;
}

export interface ILlmClient {
  provider: LlmProvider;
  generate(prompt: string, options?: LlmGenerateOptions): Promise<string>;
  isAvailable(): Promise<boolean>;
}
