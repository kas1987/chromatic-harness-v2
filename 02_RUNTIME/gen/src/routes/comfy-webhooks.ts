import { Router, Request, Response } from "express";
import type { ComfyEventBridge } from "../core/comfy-event-bridge";

export const comfyWebhooksRouter = Router();

let bridge: ComfyEventBridge | null = null;

export function initializeComfyWebhooksRouter(eventBridge: ComfyEventBridge): void {
  bridge = eventBridge;
}

interface WebhookPayload {
  event_type: string;
  job_id: string;
  data?: unknown;
}

function validatePayload(body: unknown): body is WebhookPayload {
  if (!body || typeof body !== "object") return false;
  const b = body as Record<string, unknown>;
  return typeof b.event_type === "string" && b.event_type.length > 0;
}

// POST /comfy/webhook
comfyWebhooksRouter.post("/webhook", async (req: Request, res: Response) => {
  if (!validatePayload(req.body)) {
    return res.status(400).json({ error: "event_type (string) is required" });
  }

  const { event_type, job_id = "", data = {} } = req.body as WebhookPayload;

  if (!bridge) {
    // Bridge not initialized — log inline and return accepted
    console.warn("[comfy-webhook] Bridge not initialized; event dropped:", event_type);
    return res.status(202).json({ accepted: true, classified: false, note: "bridge_unavailable" });
  }

  try {
    const evt = await bridge.ingest(event_type, job_id, data);
    return res.json({
      accepted: true,
      timestamp: evt.timestamp,
      event_type: evt.event_type,
      job_id: evt.job_id,
      classification: evt.classification ?? null,
    });
  } catch (err) {
    console.error("[comfy-webhook] ingest error:", err);
    return res.status(500).json({ error: "Failed to ingest event" });
  }
});
