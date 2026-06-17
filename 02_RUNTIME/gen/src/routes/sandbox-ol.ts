import { Request, Response, Router } from "express";
import Database from "better-sqlite3";
import {
  SANDBOX_OL_ALLOWED_AGENTS,
  SandboxOlBridgeService,
  type SandboxOlAgent,
} from "../services/sandbox-ol-bridge.js";

export const sandboxOlRouter = Router();

let _service: SandboxOlBridgeService | null = null;

export function initializeSandboxOlRouter(db: Database.Database | null = null): void {
  _service = new SandboxOlBridgeService(db);
}

function service(): SandboxOlBridgeService {
  if (!_service) {
    _service = new SandboxOlBridgeService(null);
  }
  return _service;
}

function isAllowedAgent(value: string): value is SandboxOlAgent {
  return (SANDBOX_OL_ALLOWED_AGENTS as readonly string[]).includes(value);
}

sandboxOlRouter.get("/health", (_req: Request, res: Response) => {
  res.json(service().health());
});

sandboxOlRouter.get("/agents", (_req: Request, res: Response) => {
  res.json({ agents: SANDBOX_OL_ALLOWED_AGENTS });
});

sandboxOlRouter.post("/delegate", async (req: Request, res: Response) => {
  const body = req.body as {
    agent?: string;
    prompt?: string;
    context?: Record<string, unknown>;
    provider?: "auto" | "mock" | "anthropic" | "openai" | "ollama";
    model?: string;
    live?: boolean;
    timeoutMs?: number;
    ollamaHost?: string;
  };

  if (!body?.agent || typeof body.agent !== "string" || !isAllowedAgent(body.agent)) {
    return res.status(400).json({
      error: "agent must be one of the allowlisted sandbox agents",
      allowedAgents: SANDBOX_OL_ALLOWED_AGENTS,
    });
  }

  if (!body?.prompt || typeof body.prompt !== "string" || !body.prompt.trim()) {
    return res.status(400).json({ error: "prompt is required" });
  }

  const traceId = `sandbox-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
  const startedAt = Date.now();

  try {
    const result = await service().delegate({
      agent: body.agent,
      prompt: body.prompt,
      context: body.context,
      provider: body.provider,
      model: body.model,
      live: body.live,
      timeoutMs: body.timeoutMs,
      ollamaHost: body.ollamaHost,
    });

    return res.json(result);
  } catch (err) {
    service().logFailure({
      traceId,
      agent: body.agent,
      latencyMs: Date.now() - startedAt,
      error: err instanceof Error ? err.message : String(err),
    });
    return res.status(502).json({
      error: err instanceof Error ? err.message : "Sandbox delegation failed",
      traceId,
    });
  }
});
