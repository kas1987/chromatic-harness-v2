import { Router, Request, Response } from "express";
import type { WebhookSource } from "../webhooks/webhook-types";
import { WebhookStore } from "../webhooks/webhook-store";
import {
  parseGitHubWebhook,
  parseCIWebhook,
  parseSlackWebhook,
  parseGenericWebhook,
} from "../webhooks/webhook-parsers";
import { ChannelBroadcaster } from "../channels/channel-broadcaster";
import Database from "better-sqlite3";

export const webhooksRouter = Router();

let webhookStore: WebhookStore | null = null;
let broadcaster: ChannelBroadcaster | null = null;

export function initializeWebhookStore(
  store: WebhookStore,
  channelBroadcaster: ChannelBroadcaster
): void {
  webhookStore = store;
  broadcaster = channelBroadcaster;
}

function getStore(): WebhookStore {
  if (!webhookStore) throw new Error("WebhookStore not initialized");
  return webhookStore;
}

function getBroadcaster(): ChannelBroadcaster {
  if (!broadcaster) throw new Error("ChannelBroadcaster not initialized");
  return broadcaster;
}

async function handleWebhook(
  source: WebhookSource,
  eventType: string,
  payload: Record<string, unknown>,
  res: Response
): Promise<void> {
  const store = getStore();
  const bc = getBroadcaster();

  // 1. Parse
  let parsed;
  switch (source) {
    case "github":
      parsed = parseGitHubWebhook(eventType, payload);
      break;
    case "ci":
      parsed = parseCIWebhook(payload);
      break;
    case "slack":
      parsed = parseSlackWebhook(payload);
      break;
    default:
      parsed = parseGenericWebhook(payload);
  }

  // 2. Store (unprocessed)
  const event = store.recordEvent({
    source,
    eventType: parsed.eventType,
    payload,
    processed: false,
  });

  // 3. If triggerTask, broadcast on "tasks" channel
  let taskCreated: string | undefined;
  if (parsed.triggerTask && parsed.taskDescription) {
    const channelEvent = bc.makeChannelEvent(
      "tasks",
      "task_requested",
      {
        title: parsed.title,
        description: parsed.taskDescription,
        severity: parsed.severity,
        webhookEventId: event.id,
        source,
      },
      "webhook"
    );
    bc.broadcast("tasks", channelEvent);
    taskCreated = channelEvent.id;
  }

  // 4. Mark processed
  store.markProcessed(event.id, taskCreated);

  // 5. Respond
  res.json({
    received: true,
    eventId: event.id,
    triggerTask: parsed.triggerTask,
  });
}

webhooksRouter.post("/github", async (req: Request, res: Response) => {
  const eventType =
    (req.headers["x-github-event"] as string | undefined) ?? "unknown";
  const payload = (req.body ?? {}) as Record<string, unknown>;
  try {
    await handleWebhook("github", eventType, payload, res);
  } catch (err) {
    console.error("Error handling GitHub webhook:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

webhooksRouter.post("/ci", async (req: Request, res: Response) => {
  const payload = (req.body ?? {}) as Record<string, unknown>;
  try {
    await handleWebhook("ci", "build", payload, res);
  } catch (err) {
    console.error("Error handling CI webhook:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

webhooksRouter.post("/slack", async (req: Request, res: Response) => {
  const payload = (req.body ?? {}) as Record<string, unknown>;
  try {
    await handleWebhook("slack", "message", payload, res);
  } catch (err) {
    console.error("Error handling Slack webhook:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

webhooksRouter.post("/generic", async (req: Request, res: Response) => {
  const payload = (req.body ?? {}) as Record<string, unknown>;
  try {
    await handleWebhook("generic", "generic", payload, res);
  } catch (err) {
    console.error("Error handling generic webhook:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

webhooksRouter.post("/comfy/image-done", (req: Request, res: Response) => {
  try {
    const bc = getBroadcaster();
    const { prompt_id, metadata, external_id } = (req.body ?? {}) as Record<string, string>;

    const payload: Record<string, unknown> = {
      promptId: String(prompt_id || ""),
      externalId: String(external_id || ""),
      metadata: (() => {
        try {
          return metadata ? JSON.parse(metadata) : {};
        } catch {
          return {};
        }
      })(),
      receivedAt: new Date().toISOString(),
    };

    const event = bc.makeChannelEvent("comfyui-jobs", "image_done", payload, "webhook");
    bc.broadcast("comfyui-jobs", event);

    res.status(200).json({ received: true, eventId: event.id });
  } catch (err) {
    console.error("Error handling ComfyUI image-done webhook:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

webhooksRouter.get("/recent", (req: Request, res: Response) => {
  try {
    const store = getStore();
    const source = req.query.source as WebhookSource | undefined;
    const limit = req.query.limit ? parseInt(req.query.limit as string, 10) : 50;
    const events = store.getRecentEvents(source, limit);
    res.json({ events });
  } catch (err) {
    console.error("Error fetching recent webhooks:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});
