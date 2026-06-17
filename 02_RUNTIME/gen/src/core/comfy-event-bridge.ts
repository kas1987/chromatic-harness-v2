import WebSocket from "ws";
import fs from "fs";
import path from "path";
import { ChannelBroadcaster } from "../channels/channel-broadcaster";
import type { OllamaEnricher } from "../ollama/ollama-enricher";

const QUEUE_EVENT_TYPES = new Set(["status"]);

export interface ComfyEvent {
  timestamp: string;
  event_type: string;
  job_id: string;
  data: unknown;
  classification?: string;
}

/**
 * Resolves the JSONL log path relative to the repo root.
 * Uses __dirname traversal to avoid hardcoded drive paths.
 */
function resolveEventsLog(): string {
  // gen/src/core → gen/src → gen → repo root
  const repoRoot = path.resolve(__dirname, "..", "..", "..");
  return path.join(repoRoot, ".agents", "crank", "events.jsonl");
}

export class ComfyEventBridge {
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private stopped = false;
  private readonly eventsLogPath: string;

  constructor(
    private readonly comfyUrl: string,
    private readonly broadcaster: ChannelBroadcaster,
    private readonly ollamaEnricher?: OllamaEnricher | null,
  ) {
    this.eventsLogPath = resolveEventsLog();
    this.ensureLogDir();
  }

  start(): void {
    this.stopped = false;
    this.connect();
  }

  stop(): void {
    this.stopped = true;
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws !== null) {
      this.ws.removeAllListeners();
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Ingest a ComfyUI event from any source (WebSocket or HTTP webhook).
   * Classifies via Ollama if available, appends to events.jsonl, and
   * broadcasts to SSE subscribers.
   */
  async ingest(event_type: string, job_id: string, data: unknown): Promise<ComfyEvent> {
    const evt: ComfyEvent = {
      timestamp: new Date().toISOString(),
      event_type,
      job_id,
      data,
    };

    // Optional Ollama classification for critical events (fail-open)
    if (this.ollamaEnricher && (event_type === "execution_complete" || event_type === "execution_error")) {
      try {
        const tags = await this.ollamaEnricher.enrichEvent(
          "comfy_event",
          { event_type, job_id },
          event_type !== "execution_error",
        );
        if (tags) {
          evt.classification = `${tags.intent}/${tags.risk_level}`;
        }
      } catch {
        // fail-open: classification is optional
      }
    }

    this.appendToLog(evt);
    this.broadcastEvent(event_type, job_id, evt.data as Record<string, unknown>);

    return evt;
  }

  private connect(): void {
    this.ws = new WebSocket(this.comfyUrl);

    this.ws.on("open", () => {
      console.log("[comfy-bridge] Connected to ComfyUI WebSocket");
    });

    this.ws.on("message", (data, isBinary) => {
      if (isBinary) return; // skip JPEG preview frames
      try {
        const msg = JSON.parse(data.toString()) as {
          type: string;
          data: { prompt_id?: string; [key: string]: unknown };
        };
        const job_id = (msg.data as Record<string, unknown>)?.prompt_id as string ?? "";
        this.ingest(msg.type, job_id, msg.data).catch(() => {
          // fire-and-forget, errors already handled inside ingest
        });
      } catch {
        // ignore malformed JSON
      }
    });

    this.ws.on("close", () => {
      if (!this.stopped) {
        this.reconnectTimer = setTimeout(() => this.connect(), 2000);
      }
    });

    this.ws.on("error", () => {
      // error event fires before close — close handler will schedule reconnect
    });
  }

  private broadcastEvent(
    type: string,
    job_id: string,
    data: Record<string, unknown>,
  ): void {
    const channelId = QUEUE_EVENT_TYPES.has(type) ? "comfyui-queue" : "comfyui-jobs";
    const event = this.broadcaster.makeChannelEvent(
      channelId,
      type,
      { job_id, ...data },
      "internal",
    );
    this.broadcaster.broadcast(channelId, event);
  }

  private appendToLog(evt: ComfyEvent): void {
    try {
      fs.appendFileSync(this.eventsLogPath, JSON.stringify(evt) + "\n", "utf8");
    } catch (err) {
      console.warn("[comfy-bridge] Failed to write event log:", (err as Error).message);
    }
  }

  private ensureLogDir(): void {
    try {
      fs.mkdirSync(path.dirname(this.eventsLogPath), { recursive: true });
    } catch {
      // directory already exists or unwritable — handled at appendToLog time
    }
  }
}
