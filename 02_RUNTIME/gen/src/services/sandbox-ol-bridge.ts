import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import Database from "better-sqlite3";
import { config } from "../config.js";

export const SANDBOX_OL_ALLOWED_AGENTS = [
  "planner",
  "executor",
  "critic",
  "personality",
  "sandbox-architect",
  "prism-glasses",
] as const;

export type SandboxOlAgent = (typeof SANDBOX_OL_ALLOWED_AGENTS)[number];

type SandboxProvider = "auto" | "mock" | "anthropic" | "openai" | "ollama";

interface SandboxDelegateRequest {
  agent: SandboxOlAgent;
  prompt: string;
  context?: Record<string, unknown>;
  provider?: SandboxProvider;
  model?: string;
  live?: boolean;
  timeoutMs?: number;
  ollamaHost?: string;
}

interface SandboxDelegateResponse {
  ok: true;
  agent: SandboxOlAgent;
  provider: string;
  model: string;
  summary: string;
  recommendations: Array<{ priority: string; title: string; action: string }>;
  metadata: Record<string, unknown>;
  elapsedMs: number;
  traceId: string;
  capturedStdout?: string;
}

interface SandboxHealth {
  ok: boolean;
  scriptPath: string;
  pythonPath: string;
  availableAgents: readonly SandboxOlAgent[];
  enabled: boolean;
}

function resolveScriptPath(): string {
  if (config.sandboxDelegateScript && path.isAbsolute(config.sandboxDelegateScript)) {
    return config.sandboxDelegateScript;
  }

  const candidates = [
    config.sandboxDelegateScript,
    "../sandbox/harness/ol_delegate.py",
    "sandbox/harness/ol_delegate.py",
  ].filter(Boolean) as string[];

  for (const candidate of candidates) {
    const resolved = path.resolve(process.cwd(), candidate);
    if (fs.existsSync(resolved)) {
      return resolved;
    }
  }

  return path.resolve(process.cwd(), "sandbox/harness/ol_delegate.py");
}

export class SandboxOlBridgeService {
  private readonly scriptPath: string;
  private readonly pythonPath: string;
  private readonly pythonArgs: string[];
  private readonly defaultTimeoutMs: number;
  private readonly db: Database.Database | null;

  constructor(db: Database.Database | null = null) {
    this.scriptPath = resolveScriptPath();
    this.pythonPath = config.sandboxDelegatePython;
    this.pythonArgs = config.sandboxDelegatePythonArgs
      .split(" ")
      .map((item) => item.trim())
      .filter(Boolean);
    this.defaultTimeoutMs = Math.max(1_000, config.sandboxDelegateTimeoutMs || 90_000);
    this.db = db;

    if (this.db) {
      this.db
        .prepare(
          `CREATE TABLE IF NOT EXISTS sandbox_delegate_log (
             id TEXT PRIMARY KEY,
             created_at TEXT NOT NULL,
             agent TEXT NOT NULL,
             provider TEXT,
             model TEXT,
             success INTEGER NOT NULL,
             latency_ms REAL NOT NULL,
             error TEXT
           )`,
        )
        .run();
    }
  }

  health(): SandboxHealth {
    return {
      ok: fs.existsSync(this.scriptPath),
      scriptPath: this.scriptPath,
      pythonPath: this.pythonPath,
      availableAgents: SANDBOX_OL_ALLOWED_AGENTS,
      enabled: true,
    };
  }

  async delegate(input: SandboxDelegateRequest): Promise<SandboxDelegateResponse> {
    const traceId = `sandbox-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
    const startedAt = Date.now();
    const timeoutMs = Math.max(1_000, input.timeoutMs ?? this.defaultTimeoutMs);

    const payload = {
      agent: input.agent,
      prompt: input.prompt,
      context: input.context ?? {},
      provider: input.provider ?? "auto",
      model: input.model,
      live: Boolean(input.live),
      ollama_host: input.ollamaHost,
      trace_id: traceId,
    };

    const result = await this.runPython(payload, timeoutMs);
    const elapsedMs = Date.now() - startedAt;

    const response: SandboxDelegateResponse = {
      ok: true,
      agent: input.agent,
      provider: String(result.provider ?? "mock"),
      model: String(result.model ?? "unknown"),
      summary: String(result.summary ?? ""),
      recommendations: Array.isArray(result.recommendations)
        ? (result.recommendations as Array<{ priority: string; title: string; action: string }>)
        : [],
      metadata:
        result.metadata && typeof result.metadata === "object"
          ? (result.metadata as Record<string, unknown>)
          : {},
      elapsedMs,
      traceId,
      capturedStdout:
        typeof result.captured_stdout === "string" && result.captured_stdout.trim()
          ? result.captured_stdout
          : undefined,
    };

    this.logRun({
      id: traceId,
      createdAt: new Date().toISOString(),
      agent: input.agent,
      provider: response.provider,
      model: response.model,
      success: 1,
      latencyMs: elapsedMs,
      error: null,
    });

    return response;
  }

  private async runPython(payload: Record<string, unknown>, timeoutMs: number): Promise<Record<string, unknown>> {
    if (!fs.existsSync(this.scriptPath)) {
      throw new Error(`Sandbox delegate script not found: ${this.scriptPath}`);
    }

    return await new Promise<Record<string, unknown>>((resolve, reject) => {
      const args = [...this.pythonArgs, this.scriptPath];
      const child = spawn(this.pythonPath, args, {
        stdio: ["pipe", "pipe", "pipe"],
        cwd: process.cwd(),
      });

      let stdout = "";
      let stderr = "";
      let completed = false;

      const timer = setTimeout(() => {
        if (!completed) {
          child.kill("SIGKILL");
          reject(new Error(`Sandbox delegate timed out after ${timeoutMs}ms`));
        }
      }, timeoutMs);

      child.stdout.on("data", (chunk) => {
        stdout += chunk.toString();
      });

      child.stderr.on("data", (chunk) => {
        stderr += chunk.toString();
      });

      child.on("error", (err) => {
        clearTimeout(timer);
        reject(err);
      });

      child.on("close", (code) => {
        completed = true;
        clearTimeout(timer);

        if (code !== 0) {
          reject(new Error(`Sandbox delegate failed (exit ${code}): ${stderr || stdout}`));
          return;
        }

        const lines = stdout
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter(Boolean);

        for (let i = lines.length - 1; i >= 0; i -= 1) {
          try {
            const parsed = JSON.parse(lines[i]) as Record<string, unknown>;
            resolve(parsed);
            return;
          } catch {
            // Keep scanning backwards until a JSON line is found.
          }
        }

        reject(new Error(`Sandbox delegate returned no JSON payload. stdout=${stdout} stderr=${stderr}`));
      });

      child.stdin.write(JSON.stringify(payload));
      child.stdin.end();
    });
  }

  logFailure(input: { traceId: string; agent: SandboxOlAgent; latencyMs: number; error: string }): void {
    this.logRun({
      id: input.traceId,
      createdAt: new Date().toISOString(),
      agent: input.agent,
      provider: null,
      model: null,
      success: 0,
      latencyMs: input.latencyMs,
      error: input.error,
    });
  }

  private logRun(entry: {
    id: string;
    createdAt: string;
    agent: string;
    provider: string | null;
    model: string | null;
    success: number;
    latencyMs: number;
    error: string | null;
  }): void {
    if (!this.db) {
      return;
    }

    this.db
      .prepare(
        `INSERT OR REPLACE INTO sandbox_delegate_log (
           id, created_at, agent, provider, model, success, latency_ms, error
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        entry.id,
        entry.createdAt,
        entry.agent,
        entry.provider,
        entry.model,
        entry.success,
        entry.latencyMs,
        entry.error,
      );
  }
}
