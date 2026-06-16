import type { ILlmClient, LlmGenerateOptions } from "../llm/llm-types.js";

/**
 * MiniMax client — wraps OpenAI-compatible chat completions endpoint.
 *
 * Two usage modes (same client, different env vars):
 *
 *   1. Ollama cloud (recommended for local setup):
 *      GEN_MINIMAX_URL=http://127.0.0.1:11434/v1
 *      GEN_MINIMAX_MODEL=minimax-m2.5:cloud
 *      Setup: ollama pull minimax-m2.5:cloud
 *      Note: Ollama routes the :cloud tag to MiniMax's infrastructure — NOT local inference.
 *
 *   2. Direct MiniMax API:
 *      GEN_MINIMAX_URL=https://api.minimax.chat/v1
 *      GEN_MINIMAX_API_KEY=<your-key>
 *      GEN_MINIMAX_MODEL=abab6.5-chat  (or check platform.minimax.io for current model IDs)
 *
 * MiniMax-M2.5 is 229B MoE (mixture-of-experts). Cloud-only — local GGUF requires 101GB+
 * RAM/VRAM, not viable on RTX 4070 (12 GB). Preferred for large-context tasks (>50K tokens)
 * where Ollama's 32K context limit is insufficient.
 *
 * Routing trigger: gen/src/llm/llm-selector.ts selectBestLlm() routes tasks with
 * estimatedInputTokens > 50_000 to MiniMax (when enabled and available).
 */
export class MiniMaxClient implements ILlmClient {
  readonly provider = "minimax" as const;

  constructor(
    private readonly baseUrl: string,
    private readonly model: string,
    private readonly apiKey: string = "",
  ) {}

  async generate(prompt: string, options?: LlmGenerateOptions): Promise<string> {
    const resp = await fetch(`${this.baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(this.apiKey ? { Authorization: `Bearer ${this.apiKey}` } : {}),
      },
      body: JSON.stringify({
        model: this.model,
        max_tokens: options?.maxTokens ?? 2048,
        temperature: options?.temperature ?? 0.7,
        messages: [{ role: "user", content: prompt }],
      }),
      // 60s timeout — cloud model round-trip is slower than local Ollama (avgLatencyMs: 2500)
      signal: AbortSignal.timeout(60_000),
    });

    if (!resp.ok) {
      const body = await resp.text().catch(() => "(unreadable)");
      throw new Error(`MiniMax API error ${resp.status}: ${body}`);
    }

    const data = (await resp.json()) as {
      choices: Array<{ message: { content: string } }>;
    };
    return data.choices[0]?.message?.content ?? "";
  }

  /**
   * Probe availability with dual-path detection:
   *
   *   Ollama cloud path: model IDs contain "minimax" (e.g., "minimax-m2.5:cloud")
   *   Direct API path:   model IDs may NOT contain "minimax" (e.g., "abab6.5-chat")
   *                      Fall back: treat any non-empty model list + apiKey as available.
   *
   * Fails open (returns false) on any network or parse error — never throws.
   */
  async isAvailable(): Promise<boolean> {
    try {
      const resp = await fetch(`${this.baseUrl}/models`, {
        headers: this.apiKey ? { Authorization: `Bearer ${this.apiKey}` } : {},
        signal: AbortSignal.timeout(3_000),
      });
      if (!resp.ok) return false;

      const data = (await resp.json()) as {
        data?: Array<{ id: string }>;
      };
      const models: string[] = data.data?.map((m) => m.id) ?? [];

      // Ollama cloud path: model ID contains "minimax"
      if (models.some((id) => id.toLowerCase().includes("minimax"))) return true;

      // Direct API path: any non-empty model list + explicit API key = treat as available
      // (the URL+key combo is the availability signal; model IDs use MiniMax-internal names)
      if (this.apiKey && models.length > 0) return true;

      return false;
    } catch {
      return false;
    }
  }
}
