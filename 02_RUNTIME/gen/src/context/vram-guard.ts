/**
 * RTX 4070 VRAM-aware session mode detection.
 *
 * The RTX 4070 has 12 GB VRAM shared between:
 *   - ComfyUI (5-11 GB during active generation)
 *   - Ollama / LM Studio (2-12 GB depending on model)
 *   - Windows desktop overhead (~0.5 GB)
 *
 * When ComfyUI is actively generating, Ollama cannot safely coexist in VRAM.
 * This guard tracks the session mode and advises the routing layer on whether
 * local LLM inference is safe or should be deferred to Max plan (cloud).
 */

export type SessionMode =
  | "heavy"     // ComfyUI actively generating — local LLMs must yield
  | "light"     // ComfyUI idle or queued — small local models safe
  | "idle";     // User not active — full autonomous capacity, time-slice VRAM

export interface VramProfile {
  mode: SessionMode;
  /** Estimated VRAM available for local LLM inference (GB). */
  availableVramGb: number;
  /** Whether Ollama lightweight models (≤7B) can run safely. */
  ollamaLightSafe: boolean;
  /** Whether LM Studio heavy models (≥14B) can run safely. */
  lmStudioSafe: boolean;
  /** Whether to disable the Ollama PlanningGate. */
  disablePlanningGate: boolean;
  /** Human-readable recommendation for the routing layer. */
  note: string;
}

/**
 * VRAM profiles per session mode for RTX 4070 (12 GB).
 * Adjust TOTAL_VRAM_GB if using a different GPU.
 */
const TOTAL_VRAM_GB = 12;

const PROFILES: Record<SessionMode, VramProfile> = {
  heavy: {
    mode: "heavy",
    availableVramGb: Math.max(0, TOTAL_VRAM_GB - 9), // ComfyUI peaks at ~9GB
    ollamaLightSafe: false,
    lmStudioSafe: false,
    disablePlanningGate: true,
    note: "ComfyUI active — route all LLM tasks to Claude Max plan. Local inference disabled.",
  },
  light: {
    mode: "light",
    availableVramGb: Math.max(0, TOTAL_VRAM_GB - 1), // ComfyUI idle, model unloaded
    ollamaLightSafe: true,
    lmStudioSafe: false,   // 14B+ models need 8+ GB — too close to ComfyUI model reload
    disablePlanningGate: false,
    note: "ComfyUI idle — Ollama (≤7B) available. LM Studio deferred. Claude for heavy tasks.",
  },
  idle: {
    mode: "idle",
    availableVramGb: TOTAL_VRAM_GB - 1, // Reserve 1GB for desktop overhead
    ollamaLightSafe: true,
    lmStudioSafe: true,   // Time-slice: run between ComfyUI batches
    disablePlanningGate: false,
    note: "Idle mode — full local capacity. Time-slice VRAM between ComfyUI batches and LLM tasks.",
  },
};

/**
 * Detects the current session mode from environment / queue state.
 *
 * Detection heuristics (in priority order):
 *   1. GEN_SESSION_MODE env var (explicit override for idle/scheduled runs)
 *   2. ComfyUI queue depth (queried from hook telemetry if available)
 *   3. Default: "light" (conservative — don't risk VRAM clash)
 */
export function detectSessionMode(): SessionMode {
  // Explicit override — set by cron/scheduler when user goes idle
  const envMode = process.env.GEN_SESSION_MODE as SessionMode | undefined;
  if (envMode && ["heavy", "light", "idle"].includes(envMode)) {
    return envMode;
  }
  // Default: light (safe for Ollama 7B, defers LM Studio)
  return "light";
}

export function getVramProfile(mode?: SessionMode): VramProfile {
  return PROFILES[mode ?? detectSessionMode()];
}

/**
 * Returns the safest Ollama model given the current session mode.
 *
 * heavy → qwen3:4b       (2GB, CPU-safe while ComfyUI is using VRAM)
 * light → qwen2.5-coder:7b  (4GB, fits alongside idle ComfyUI)
 * idle  → qwen2.5-coder:14b (8GB, time-sliced with ComfyUI batches)
 *
 * Overridable via GEN_OLLAMA_MODEL_HEAVY/LIGHT/IDLE env vars.
 */
export function safeOllamaModel(mode: SessionMode): string {
  switch (mode) {
    case "idle":  return process.env.GEN_OLLAMA_MODEL_IDLE   ?? "qwen2.5-coder:14b";
    case "light": return process.env.GEN_OLLAMA_MODEL_LIGHT  ?? "qwen2.5-coder:7b";
    case "heavy": return process.env.GEN_OLLAMA_MODEL_HEAVY  ?? "qwen3:4b";
  }
}

/**
 * Returns the local embedding model (for Gen memory/RAG when embeddings
 * are needed without an OpenAI API call).
 */
export function localEmbedModel(): string {
  return process.env.GEN_OLLAMA_EMBED_MODEL ?? "nomic-embed-text";
}
