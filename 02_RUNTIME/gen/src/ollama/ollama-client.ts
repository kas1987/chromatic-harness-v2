import fetch from "node-fetch";

export interface OllamaGenerateOptions {
  temperature?: number;
  seed?: number;
  num_predict?: number;
}

export interface OllamaGenerateResponse {
  model: string;
  response: string;
  done: boolean;
}

export class OllamaClient {
  private baseUrl: string;
  private timeoutMs: number;

  constructor(baseUrl = "http://127.0.0.1:11434", timeoutMs = 10_000) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.timeoutMs = timeoutMs;
  }

  async isAvailable(): Promise<boolean> {
    try {
      const controller = new AbortController();
      const id = setTimeout(() => controller.abort(), 2_000);
      const res = await fetch(`${this.baseUrl}/api/tags`, {
        signal: controller.signal as any,
      });
      clearTimeout(id);
      return res.ok;
    } catch {
      return false;
    }
  }

  async listModels(): Promise<string[]> {
    try {
      const controller = new AbortController();
      const id = setTimeout(() => controller.abort(), 5_000);
      const res = await fetch(`${this.baseUrl}/api/tags`, {
        signal: controller.signal as any,
      });
      clearTimeout(id);
      if (!res.ok) return [];
      const data = (await res.json()) as { models?: Array<{ name: string }> };
      return (data.models ?? []).map((m) => m.name);
    } catch {
      return [];
    }
  }

  async generate(
    model: string,
    prompt: string,
    options?: OllamaGenerateOptions,
  ): Promise<string | null> {
    try {
      const controller = new AbortController();
      const id = setTimeout(() => controller.abort(), this.timeoutMs);
      const res = await fetch(`${this.baseUrl}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model, prompt, stream: false, options: options ?? {} }),
        signal: controller.signal as any,
      });
      clearTimeout(id);
      if (!res.ok) return null;
      const data = (await res.json()) as OllamaGenerateResponse;
      return data.response ?? null;
    } catch {
      return null;
    }
  }

  /**
   * Returns locally available models suitable for text generation.
   * Excludes embedding, vision, tagger, and coder-specific models.
   */
  async listTextGenModels(): Promise<string[]> {
    const all = await this.listModels();
    const EXCLUDE = ["embed", "tagger", "coder", "vl", "llava", "nomic"];
    return all.filter(
      (m) => !EXCLUDE.some((ex) => m.toLowerCase().includes(ex)),
    );
  }

  async generateJSON<T>(
    model: string,
    prompt: string,
    options?: OllamaGenerateOptions,
  ): Promise<T | null> {
    const raw = await this.generate(model, prompt, { temperature: 0.1, ...options });
    if (!raw) return null;
    const match = raw.match(/\{[\s\S]*\}/);
    if (!match) return null;
    try {
      return JSON.parse(match[0]) as T;
    } catch {
      return null;
    }
  }
}
