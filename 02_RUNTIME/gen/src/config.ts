export const config = {
  port: parseInt(process.env.GEN_PORT || "43123", 10),
  nodeEnv: process.env.NODE_ENV || "development",
  databasePath: process.env.DATABASE_PATH || "./gen.db",
  // No fallback — an absent/dev token is caught at startup and by authMiddleware.
  genToken: process.env.GEN_TOKEN ?? "",
  adminToken: process.env.GEN_ADMIN_TOKEN ?? process.env.GEN_TOKEN ?? "",
  embeddingUrl: process.env.GEN_EMBEDDING_URL || "https://api.openai.com/v1/embeddings",
  embeddingKey: process.env.GEN_EMBEDDING_KEY || "",
  embeddingModel: process.env.GEN_EMBEDDING_MODEL || "text-embedding-3-small",
  enableEmbeddings: Boolean(process.env.GEN_EMBEDDING_KEY),
  comfyUrl: process.env.GEN_COMFY_URL || "ws://127.0.0.1:8188/ws",
  enableComfyBridge: process.env.GEN_COMFY_BRIDGE !== "false",
  ollamaUrl: process.env.GEN_OLLAMA_URL || "http://127.0.0.1:11434",
  ollamaModel: process.env.GEN_OLLAMA_MODEL || "qwen3:4b",  // qwen2.5:7b not installed; qwen3:4b is the installed light-tier default
  enableOllama: process.env.GEN_ENABLE_OLLAMA === "true",
  /** Google Gemma on Ollama — dedicated tag (not GEN_OLLAMA_MODEL). Pull e.g. `ollama pull gemma3:4b`. */
  gemmaOllamaModel: process.env.GEN_GEMMA_OLLAMA_MODEL || "gemma3:4b",
  /** After pulling Gemma into Ollama, set true so /api/delegate and routing can select provider `gemma`. */
  enableGemma: process.env.GEN_ENABLE_GEMMA === "true",
  anthropicApiKey: process.env.ANTHROPIC_API_KEY || "",
  gptApiKey: process.env.OPENAI_API_KEY || "",
  gptModel: process.env.GEN_GPT_MODEL || "gpt-4o-mini",
  geminiApiKey: process.env.GEMINI_API_KEY || "",
  geminiModel: process.env.GEN_GEMINI_MODEL || "gemini-2.0-flash-lite",
  // LM Studio — local OpenAI-compatible server (default port 1234)
  lmStudioUrl: process.env.GEN_LM_STUDIO_URL || "http://localhost:1234/v1",
  lmStudioModel: process.env.GEN_LM_STUDIO_MODEL || "qwen2.5-coder-32b",
  // MiniMax — 229B MoE cloud provider. Cloud-only (local GGUF requires 101GB+ RAM/VRAM).
  // Ollama cloud mode: set GEN_MINIMAX_URL=http://127.0.0.1:11434/v1 + ollama pull minimax-m2.5:cloud
  // Direct API mode: set GEN_MINIMAX_URL=https://api.minimax.chat/v1 + GEN_MINIMAX_API_KEY=<key>
  miniMaxUrl:    process.env.GEN_MINIMAX_URL     || "http://127.0.0.1:11434/v1",
  miniMaxModel:  process.env.GEN_MINIMAX_MODEL   || "minimax-m2.5:cloud",
  miniMaxApiKey: process.env.GEN_MINIMAX_API_KEY || "",
  enableMiniMax: process.env.GEN_ENABLE_MINIMAX  === "true",
  ttsUrl: process.env.TTS_URL ?? "http://127.0.0.1:8765",
  enableTts: process.env.GEN_ENABLE_TTS === "true",
  ttsMode: (process.env.GEN_TTS_MODE === "ia" ? "ia" : "direct") as "direct" | "ia",  // runtime guard
  ttsDefaultVoice: process.env.TTS_DEFAULT_VOICE ?? "UA___20s_Woman",
  ttsAudioDir: process.env.TTS_AUDIO_DIR ?? "./audio",
  ttsTimeoutMs: Number(process.env.TTS_TIMEOUT_MS ?? "30000"),  // 30s for cold-start tolerance
  ingestEnabled: process.env.GEN_INGEST_ENABLED !== 'false',
  ingestMaxBatchSize: parseInt(process.env.GEN_INGEST_MAX_BATCH ?? '100', 10),
  synthesisOutputDir: process.env.GEN_SYNTHESIS_OUTPUT ?? '.agents/inbox',
  synthesisWindowHours: parseInt(process.env.GEN_SYNTHESIS_WINDOW_HOURS ?? '6', 10),
  // BUDGET_POLICY: Budget enforcement mode.
  // "normalized" (default): lenient, warnings up to 120% soft cap, then block. Use for development.
  // "aggressive": strict cost limits, auto-fallback, hard stops at 95%. Use for production/batch jobs.
  budgetPolicy: process.env.BUDGET_POLICY ?? "normalized",
  // Periodic memory-consolidation nudge (Hermes-inspired).
  // Fires every N user-prompts per session. 0 = disabled.
  nudgeInterval: parseInt(process.env.GEN_NUDGE_INTERVAL ?? "5", 10),
  nudgeTtlMs: parseInt(process.env.GEN_NUDGE_TTL_MS ?? String(10 * 60 * 1000), 10),
  sandboxDelegatePython: process.env.GEN_SANDBOX_DELEGATE_PYTHON || "py",
  sandboxDelegatePythonArgs: process.env.GEN_SANDBOX_DELEGATE_PYTHON_ARGS || "-3.11",
  sandboxDelegateScript: process.env.GEN_SANDBOX_DELEGATE_SCRIPT || "",
  sandboxDelegateTimeoutMs: parseInt(process.env.GEN_SANDBOX_DELEGATE_TIMEOUT_MS ?? "90000", 10),
};
