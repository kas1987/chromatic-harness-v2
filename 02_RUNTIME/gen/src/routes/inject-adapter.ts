import { randomUUID } from "crypto";
import { Router, Request, Response } from "express";
import { config } from "../config.js";

export const injectAdapterRouter = Router();

interface InjectSubtask {
  id?: string;
  title?: string;
  description?: string;
  effort?: string;
  depends_on?: string[];
}

interface InjectDispatchPayload {
  dispatch_id: string;
  refactored_message: string;
  priority?: "low" | "medium" | "high";
  original_message?: string;
  source?: string;
  timestamp?: string;
  technical_review?: Record<string, unknown>;
  subtasks?: InjectSubtask[];
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function compactSubtasks(subtasks: InjectSubtask[] | undefined, max = 8): string {
  if (!subtasks || subtasks.length === 0) {
    return "none";
  }

  return subtasks
    .slice(0, max)
    .map((task, idx) => {
      const id = asString(task.id, `task_${idx + 1}`);
      const title = asString(task.title, "untitled");
      const effort = asString(task.effort, "unknown");
      return `${id}: ${title} [effort=${effort}]`;
    })
    .join("\n");
}

function buildDispatchPrompt(payload: InjectDispatchPayload): string {
  const priority = payload.priority ?? "medium";
  const refactored = payload.refactored_message.trim();
  const original = asString(payload.original_message, "").trim();
  const review = payload.technical_review
    ? JSON.stringify(payload.technical_review).slice(0, 3000)
    : "{}";
  const subtasks = compactSubtasks(payload.subtasks);

  return [
    `Inject dispatch request ${payload.dispatch_id}`,
    `priority=${priority}`,
    "",
    "Refactored message:",
    refactored,
    "",
    "Original message:",
    original || "none",
    "",
    "Technical review (json):",
    review,
    "",
    "Subtasks:",
    subtasks,
  ].join("\n");
}

injectAdapterRouter.post("/dispatch", async (req: Request, res: Response) => {
  const payload = (req.body ?? {}) as Partial<InjectDispatchPayload>;

  const dispatchId = asString(payload.dispatch_id).trim();
  const refactored = asString(payload.refactored_message).trim();

  if (!dispatchId) {
    return res.status(400).json({ error: "dispatch_id is required" });
  }
  if (!refactored) {
    return res.status(400).json({ error: "refactored_message is required" });
  }
  if (!config.genToken) {
    return res.status(503).json({ error: "GEN token not configured for internal dispatch" });
  }

  const internalBody = {
    prompt: buildDispatchPrompt(payload as InjectDispatchPayload),
    sessionId: `inject-${dispatchId}`,
    metadata: {
      intent_tag: "dispatch",
      source_skill: "inject-adapter",
      inject_dispatch_id: dispatchId,
      inject_priority: payload.priority ?? "medium",
      inject_source: asString(payload.source, "inject"),
    },
  };

  try {
    const hookResp = await fetch(`http://127.0.0.1:${config.port}/hooks/user-prompt`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${config.genToken}`,
      },
      body: JSON.stringify(internalBody),
      signal: AbortSignal.timeout(15_000),
    });

    if (!hookResp.ok) {
      const detail = await hookResp.text();
      return res.status(502).json({
        error: "Failed to forward dispatch into hook pipeline",
        status: hookResp.status,
        detail: detail.slice(0, 1200),
      });
    }

    const forwarded = (await hookResp.json()) as Record<string, unknown>;
    const hop =
      forwarded &&
      typeof forwarded === "object" &&
      forwarded.hop &&
      typeof forwarded.hop === "object"
        ? forwarded.hop
        : undefined;
    return res.status(202).json({
      accepted: true,
      correlation_id: randomUUID(),
      dispatch_id: dispatchId,
      forwarded_to: "/hooks/user-prompt",
      hop_intent_tag: "dispatch",
      hop,
      hook_response: forwarded,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return res.status(502).json({
      error: "Dispatch forwarding failed",
      detail: message,
    });
  }
});
