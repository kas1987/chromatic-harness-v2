import { ILlmClient, LlmProvider, type LlmGenerateOptions } from "./llm-types.js";
import { OllamaClient } from "../ollama/ollama-client.js";
import { MiniMaxClient } from "../minimax/minimax-client.js";
import { config as appConfig } from "../config.js";

type Config = typeof appConfig;

/** Default timeout for all LLM provider calls (30 s). */
const LLM_TIMEOUT_MS = 30_000;

/** Wraps a promise with a hard timeout. Throws on expiry. */
function withTimeout<T>(promise: Promise<T>, ms = LLM_TIMEOUT_MS, label = "LLM call"): Promise<T> {
  return Promise.race([
    promise,
    new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms)
    ),
  ]);
}

// 30-second TTL availability cache shared by all clients
const _availCache = new Map<string, { v: boolean; exp: number }>();

async function cachedAvailable(key: string, check: () => Promise<boolean>): Promise<boolean> {
  const hit = _availCache.get(key);
  if (hit && hit.exp > Date.now()) return hit.v;
  const v = await check().catch(() => false);
  _availCache.set(key, { v, exp: Date.now() + 30_000 });
  return v;
}

export class ClaudeClient implements ILlmClient {
  readonly provider = "claude" as const;

  /**
   * Default model for direct generate() calls.
   * Uses haiku — cheapest tier, no session budget pressure.
   * Override by passing a different ClaudeClient instance via createClient().
   */
  constructor(private modelId = "claude-haiku-4-5-20251001") {}

  async generate(prompt: string, options?: LlmGenerateOptions): Promise<string> {
    const authKey = process.env.ANTHROPIC_API_KEY;
    if (!authKey) throw new Error("ANTHROPIC_API_KEY not set for direct Claude API calls. Under Max plan, routing suggestions are free but generate() requires an API key.");
    const { default: Anthropic } = await import("@anthropic-ai/sdk");
    const client = new Anthropic({ ["apiKey"]: authKey });
    const resp = await withTimeout(
      client.messages.create({
        model: this.modelId,
        max_tokens: options?.maxTokens ?? 1024,
        messages: [{ role: "user", content: prompt }],
      }),
      LLM_TIMEOUT_MS,
      "Claude generate()"
    );
    return resp.content[0].type === "text" ? resp.content[0].text : "";
  }

  /**
   * Always returns true — Claude Code Max plan is always active.
   * No API key required for routing suggestions (isAvailable = plan availability,
   * not API key availability). Direct generate() calls still require ANTHROPIC_API_KEY.
   */
  async isAvailable(): Promise<boolean> {
    return true;
  }
}

export class OpenAiClient implements ILlmClient {
  readonly provider = "gpt" as const;
  constructor(private cfg: Config) {}

  async generate(prompt: string, options?: LlmGenerateOptions): Promise<string> {
    if (!this.cfg.gptApiKey) throw new Error("OPENAI_API_KEY not set");
    const { default: OpenAI } = await import("openai");
    const client = new OpenAI({ ["apiKey"]: this.cfg.gptApiKey });
    const resp = await withTimeout(
      client.chat.completions.create({
        model: this.cfg.gptModel,
        max_tokens: options?.maxTokens ?? 1024,
        temperature: options?.temperature ?? 0.7,
        messages: [{ role: "user", content: prompt }],
      }),
      LLM_TIMEOUT_MS,
      "OpenAI generate()"
    );
    return resp.choices[0]?.message?.content ?? "";
  }

  async isAvailable(): Promise<boolean> {
    return cachedAvailable("gpt", async () => Boolean(this.cfg.gptApiKey));
  }
}

export class GeminiClient implements ILlmClient {
  readonly provider = "gemini" as const;
  constructor(private cfg: Config) {}

  async generate(prompt: string, options?: LlmGenerateOptions): Promise<string> {
    if (!this.cfg.geminiApiKey) throw new Error("GEMINI_API_KEY not set");
    const { GoogleGenerativeAI } = await import("@google/generative-ai");
    const genAI = new GoogleGenerativeAI(this.cfg.geminiApiKey);
    const model = genAI.getGenerativeModel({
      model: this.cfg.geminiModel,
      generationConfig: {
        maxOutputTokens: options?.maxTokens ?? 1024,
        temperature: options?.temperature ?? 0.7,
      },
    });
    const result = await withTimeout(model.generateContent(prompt), LLM_TIMEOUT_MS, "Gemini generate()");
    return result.response.text();
  }

  async isAvailable(): Promise<boolean> {
    return cachedAvailable("gemini", async () => Boolean(this.cfg.geminiApiKey));
  }
}

export class OllamaClientWrapper implements ILlmClient {
  readonly provider = "ollama" as const;
  private inner: OllamaClient;

  constructor(private cfg: Config) {
    this.inner = new OllamaClient(cfg.ollamaUrl);
  }

  async generate(prompt: string, options?: LlmGenerateOptions): Promise<string> {
    const model = options?.localModelTag?.trim() || this.cfg.ollamaModel;
    const result = await withTimeout(
      this.inner.generate(model, prompt, {
        temperature: options?.temperature ?? 0.7,
        num_predict: options?.maxTokens ?? 1024,
      }),
      LLM_TIMEOUT_MS,
      "Ollama generate()"
    );
    return result ?? "";
  }

  async isAvailable(): Promise<boolean> {
    return cachedAvailable("ollama", () => this.inner.isAvailable());
  }
}

/**
 * Google Gemma on local Ollama — same server as `ollama` but uses GEN_GEMMA_OLLAMA_MODEL.
 * Requires `ollama pull <tag>` and GEN_ENABLE_GEMMA=true.
 */
export class GemmaOllamaClient implements ILlmClient {
  readonly provider = "gemma" as const;
  private inner: OllamaClient;

  constructor(private cfg: Config) {
    this.inner = new OllamaClient(cfg.ollamaUrl);
  }

  async generate(prompt: string, options?: LlmGenerateOptions): Promise<string> {
    const model = options?.localModelTag?.trim() || this.cfg.gemmaOllamaModel;
    const result = await withTimeout(
      this.inner.generate(model, prompt, {
        temperature: options?.temperature ?? 0.7,
        num_predict: options?.maxTokens ?? 1024,
      }),
      LLM_TIMEOUT_MS,
      "Gemma (Ollama) generate()"
    );
    return result ?? "";
  }

  async isAvailable(): Promise<boolean> {
    if (!this.cfg.enableGemma) {
      return cachedAvailable("gemma", async () => false);
    }
    return cachedAvailable("gemma", async () => {
      const up = await this.inner.isAvailable();
      if (!up) return false;
      const names = await this.inner.listModels();
      const want = this.cfg.gemmaOllamaModel.trim();
      const wLower = want.toLowerCase();
      const base = want.split(":")[0]?.toLowerCase() ?? wLower;
      return names.some((n) => {
        const nl = n.toLowerCase();
        return nl === wLower || nl.startsWith(`${base}:`);
      });
    });
  }
}

/**
 * LM Studio — local OpenAI-compatible server.
 *
 * Runs heavy models (qwen2.5-coder:32b, deepseek-coder, etc.) on local hardware.
 * No API key required. Configure via GEN_LM_STUDIO_URL + GEN_LM_STUDIO_MODEL.
 *
 * Start LM Studio, load a model, enable "Local Server" in the app, then set:
 *   GEN_LM_STUDIO_URL=http://localhost:1234/v1
 *   GEN_LM_STUDIO_MODEL=qwen2.5-coder-32b
 */
export class LmStudioClient implements ILlmClient {
  readonly provider = "lm-studio" as const;

  constructor(private cfg: Config) {}

  async generate(prompt: string, options?: LlmGenerateOptions): Promise<string> {
    const { default: OpenAI } = await import("openai");
    const client = new OpenAI({
      baseURL: this.cfg.lmStudioUrl,
      ["apiKey"]: "lm-studio", // LM Studio ignores the key but the SDK requires a non-empty string
    });
    const resp = await withTimeout(
      client.chat.completions.create({
        model: this.cfg.lmStudioModel,
        max_tokens: options?.maxTokens ?? 2048,
        temperature: options?.temperature ?? 0.7,
        messages: [{ role: "user", content: prompt }],
      }),
      LLM_TIMEOUT_MS,
      "LM Studio generate()"
    );
    return resp.choices[0]?.message?.content ?? "";
  }

  async isAvailable(): Promise<boolean> {
    return cachedAvailable("lm-studio", async () => {
      try {
        const resp = await fetch(`${this.cfg.lmStudioUrl}/models`, {
          signal: AbortSignal.timeout(2000),
        });
        return resp.ok;
      } catch {
        return false;
      }
    });
  }
}

export function createClient(provider: LlmProvider, cfg: Config): ILlmClient {
  switch (provider) {
    case "claude":     return new ClaudeClient();
    case "gpt":        return new OpenAiClient(cfg);
    case "gemini":     return new GeminiClient(cfg);
    case "ollama":     return new OllamaClientWrapper(cfg);
    case "gemma":      return new GemmaOllamaClient(cfg);
    case "lm-studio":  return new LmStudioClient(cfg);
    case "minimax":    return new MiniMaxClient(cfg.miniMaxUrl, cfg.miniMaxModel, cfg.miniMaxApiKey);
    default: throw new Error(`Unknown LLM provider: ${provider as string}`);
  }
}

// Export the cache for testing (TTL manipulation)
export { _availCache };
