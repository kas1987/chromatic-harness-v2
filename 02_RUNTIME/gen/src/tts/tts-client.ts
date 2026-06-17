import fetch from "node-fetch";
import fs from "fs";
import path from "path";
import { v4 as uuidv4 } from "uuid";

export interface TtsSynthesisResult {
  audioPath: string;
  voiceId: string;
  durationMs: number;
}

export interface TtsHealthResult {
  available: boolean;
  voices?: string[];
}

export class TtsSynthesisError extends Error {
  readonly statusCode?: number;

  constructor(message: string, statusCode?: number) {
    super(message);
    this.name = "TtsSynthesisError";
    this.statusCode = statusCode;
  }
}

export class TtsClient {
  private readonly baseUrl: string;
  private readonly audioDir: string;
  private readonly timeoutMs: number;

  constructor(baseUrl: string, audioDir: string, timeoutMs = 30_000) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.audioDir = audioDir;
    this.timeoutMs = timeoutMs;
  }

  async isAvailable(): Promise<boolean> {
    try {
      const controller = new AbortController();
      const id = setTimeout(() => controller.abort(), 2_000);
      const res = await fetch(`${this.baseUrl}/v1/health`, {
        signal: controller.signal as any,
      });
      clearTimeout(id);
      return res.ok;
    } catch {
      return false;
    }
  }

  async listVoices(): Promise<string[]> {
    try {
      const controller = new AbortController();
      const id = setTimeout(() => controller.abort(), 5_000);
      const res = await fetch(`${this.baseUrl}/v1/voices`, {
        signal: controller.signal as any,
      });
      clearTimeout(id);
      if (!res.ok) return [];
      const data = (await res.json()) as { voices?: string[] };
      return data.voices ?? [];
    } catch {
      return [];
    }
  }

  async synthesize(
    text: string,
    voiceId: string,
    language = "English",
  ): Promise<TtsSynthesisResult> {
    const startTime = Date.now();
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), this.timeoutMs);

    let res: import("node-fetch").Response;
    try {
      res = await fetch(`${this.baseUrl}/v1/clone/manifest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice_id: voiceId, language }),
        signal: controller.signal as any,
      });
    } catch (err: any) {
      clearTimeout(id);
      throw new TtsSynthesisError(
        `Synthesis request failed: ${err?.message ?? String(err)}`,
      );
    } finally {
      clearTimeout(id);
    }

    if (!res.ok) {
      const detail = await res.json().catch(() => ({})) as { detail?: string };
      throw new TtsSynthesisError(
        `Synthesis failed (${res.status}): ${detail.detail ?? "unknown"}`,
        res.status,
      );
    }

    const contentType = res.headers.get("content-type") ?? "";
    if (!contentType.includes("audio")) {
      throw new TtsSynthesisError(
        `Unexpected content-type: ${contentType}`,
      );
    }

    const bytes = await res.arrayBuffer();
    const filename = `${uuidv4()}.wav`;
    const filePath = path.join(this.audioDir, filename);
    await fs.promises.writeFile(filePath, Buffer.from(bytes));

    return {
      audioPath: filePath,
      voiceId,
      durationMs: Date.now() - startTime,
    };
  }

  async warmup(defaultVoice = "UA___20s_Woman"): Promise<void> {
    try {
      await this.synthesize("hello", defaultVoice);
    } catch {
      // warmup failure is non-fatal — logs handled by caller
    }
  }

  async pruneOldFiles(maxAgeMs = 4 * 60 * 60 * 1000): Promise<number> {
    const files = await fs.promises.readdir(this.audioDir);
    let pruned = 0;
    for (const f of files.filter((file) => file.endsWith(".wav"))) {
      const filePath = path.join(this.audioDir, f);
      const stat = await fs.promises.stat(filePath);
      if (Date.now() - stat.mtimeMs > maxAgeMs) {
        await fs.promises.unlink(filePath);
        pruned++;
      }
    }
    return pruned;
  }
}
