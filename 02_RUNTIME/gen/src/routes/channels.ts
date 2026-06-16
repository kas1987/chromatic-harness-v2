import { Router, Request, Response } from "express";
import { randomUUID } from "crypto";
import { ChannelBroadcaster } from "../channels/channel-broadcaster";

export const channelsRouter = Router();

let broadcaster: ChannelBroadcaster | null = null;

export function initializeChannelBroadcaster(bc: ChannelBroadcaster): void {
  broadcaster = bc;
}

function getBroadcaster(): ChannelBroadcaster {
  if (!broadcaster) throw new Error("ChannelBroadcaster not initialized");
  return broadcaster;
}

// SSE subscribe
channelsRouter.get("/subscribe/:channelId", (req: Request, res: Response) => {
  const bc = getBroadcaster();
  const { channelId } = req.params;
  const sessionId =
    (req.query.sessionId as string | undefined) ?? randomUUID();
  const filtersRaw = (req.query.filters as string | undefined) ?? "";
  const filters = filtersRaw
    ? filtersRaw.split(",").map((f) => f.trim()).filter(Boolean)
    : [];

  // SSE headers
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders();

  // Initial connected event
  res.write(`data: ${JSON.stringify({ type: "connected" })}\n\n`);

  // Register subscriber
  bc.subscribe(sessionId, channelId, filters, res);

  // Heartbeat every 30s
  const heartbeat = setInterval(() => {
    try {
      res.write(`data: ${JSON.stringify({ type: "heartbeat" })}\n\n`);
      // Update lastHeartbeatAt via a no-op broadcast that just refreshes the timestamp
      const subs = bc.getActiveSubscribers();
      const sub = subs.find((s) => s.sessionId === sessionId);
      if (sub) {
        sub.lastHeartbeatAt = new Date().toISOString();
      }
    } catch {
      clearInterval(heartbeat);
    }
  }, 30_000);

  // Cleanup on disconnect
  req.on("close", () => {
    clearInterval(heartbeat);
    bc.unsubscribe(sessionId);
  });
});

// Unsubscribe
channelsRouter.post("/unsubscribe", (req: Request, res: Response) => {
  try {
    const bc = getBroadcaster();
    const { sessionId } = req.body as { sessionId?: string };
    if (!sessionId) {
      res.status(400).json({ error: "sessionId required" });
      return;
    }
    bc.unsubscribe(sessionId);
    res.json({ unsubscribed: true });
  } catch (err) {
    console.error("Error in /channels/unsubscribe:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// Broadcast (internal use, requires auth from upstream middleware)
channelsRouter.post("/broadcast", (req: Request, res: Response) => {
  try {
    const bc = getBroadcaster();
    const body = req.body as {
      channelId?: string;
      eventType?: string;
      payload?: Record<string, unknown>;
    };

    if (!body.channelId || !body.eventType) {
      res.status(400).json({ error: "channelId and eventType required" });
      return;
    }

    const event = bc.makeChannelEvent(
      body.channelId,
      body.eventType,
      body.payload ?? {},
      "admin"
    );
    bc.broadcast(body.channelId, event);
    res.json({ sent: true, eventId: event.id });
  } catch (err) {
    console.error("Error in /channels/broadcast:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// List active subscribers
channelsRouter.get("/subscribers", (_req: Request, res: Response) => {
  try {
    const bc = getBroadcaster();
    const subscribers = bc.getActiveSubscribers();
    res.json({ subscribers });
  } catch (err) {
    console.error("Error in /channels/subscribers:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});
