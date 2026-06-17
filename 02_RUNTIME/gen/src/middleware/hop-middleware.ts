import { Request, Response, NextFunction } from "express";
import { randomUUID } from "crypto";
import fs from "fs";
import path from "path";
import { HopRoute, HopEnvelope } from "../types/hop-types.js";
import { writeHopAudit } from "../utils/hop-audit.js";
import { DelegateQueue, QueueCapacityError } from "../context/delegate-queue.js";
import { ProviderCapacityTracker } from "../context/provider-capacity.js";
import { ChannelBroadcaster } from "../channels/channel-broadcaster.js";

const ROUTES_PATH = path.resolve(__dirname, "../../hop-routes.json");

// DelegateQueue is hop-local. ChannelBroadcaster is shared with /channels SSE via initializeHopBroadcaster().
const _hopCapacity = new ProviderCapacityTracker();
const hopQueue = new DelegateQueue(_hopCapacity);
let hopBroadcaster: ChannelBroadcaster = new ChannelBroadcaster();

/**
 * Wire Hop dispatches to the same ChannelBroadcaster as GET /channels/subscribe/:channelId.
 * Call once at app startup after createWebhookChannelServices().
 */
export function initializeHopBroadcaster(broadcaster: ChannelBroadcaster): void {
  hopBroadcaster = broadcaster;
}

// Routing table — loaded at startup, hot-reloaded every 30s via mtime polling
let routingRules: HopRoute[] = [];
let routesLastModified = 0;

function loadRoutes(): HopRoute[] {
  try {
    const raw = fs.readFileSync(ROUTES_PATH, "utf-8");
    const parsed = JSON.parse(raw) as { routing_rules: HopRoute[] };
    return (parsed.routing_rules ?? []).sort((a, b) => a.priority - b.priority);
  } catch {
    return []; // Missing or malformed routes → empty table (all pass-through)
  }
}

function maybeReloadRoutes(): void {
  try {
    const stat = fs.statSync(ROUTES_PATH);
    if (stat.mtimeMs > routesLastModified) {
      routesLastModified = stat.mtimeMs;
      routingRules = loadRoutes();
    }
  } catch {
    // File missing or unreadable — keep existing rules
  }
}

// Initial load + start polling (cross-platform, no SIGHUP)
routingRules = loadRoutes();
setInterval(maybeReloadRoutes, 30_000).unref();

function resolveRoute(envelope: HopEnvelope): HopRoute | null {
  for (const rule of routingRules) {
    // Skip rule if envelope confidence is below the rule's floor
    if (rule.confidence_floor > envelope.confidence) continue;

    // source_skill filter (if specified)
    if (rule.source_skill && rule.source_skill !== envelope.source_skill) continue;

    // intent_tag filter (if specified)
    if (rule.intent_tag && rule.intent_tag !== envelope.intent_tag) continue;

    // payload_pattern filter (if specified) — guard against invalid regex
    if (rule.payload_pattern) {
      try {
        const re = new RegExp(rule.payload_pattern);
        if (!re.test(envelope.payload)) continue;
      } catch {
        // Invalid regex in rule — skip rule, log and continue
        console.warn(`[hop] invalid regex in rule ${rule.rule_id}: ${rule.payload_pattern}`);
        continue;
      }
    }

    return rule; // First match wins
  }
  return null;
}

/** POST JSON envelope to GEN_HOP_REMOTE_MCP_URL (fail-open, fire-and-forget). */
async function dispatchRemoteMcp(route: HopRoute, envelope: HopEnvelope): Promise<void> {
  const base = process.env.GEN_HOP_REMOTE_MCP_URL?.trim();
  if (!base) {
    console.warn(`[hop] remote_mcp rule ${route.rule_id} skipped — set GEN_HOP_REMOTE_MCP_URL`);
    return;
  }
  const pathSeg = (route.mcp_forward_path ?? route.destination).replace(/^\/+/, "");
  const url = `${base.replace(/\/$/, "")}/${encodeURIComponent(pathSeg)}`;
  const body = {
    hop_id: envelope.hop_id,
    rule_id: route.rule_id,
    destination: route.destination,
    session_id: envelope.session_id,
    payload: envelope.payload,
    metadata: envelope.metadata,
  };
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) {
      console.warn(`[hop] remote_mcp ${url} returned ${res.status} for ${envelope.hop_id}`);
    }
  } catch (e) {
    console.warn(`[hop] remote_mcp forward failed for ${envelope.hop_id}:`, e);
  }
}

async function dispatchLocal(route: HopRoute, envelope: HopEnvelope): Promise<void> {
  const event = hopBroadcaster.makeChannelEvent(
    `hop.${route.destination}`,
    "hop.dispatch",
    {
      hop_id: envelope.hop_id,
      payload: envelope.payload,
      metadata: envelope.metadata,
    },
  );

  if (route.dispatch_mode === "async") {
    try {
      await hopQueue.enqueue(
        () => Promise.resolve(hopBroadcaster.broadcast(`hop.${route.destination}`, event)),
        { priority: "high", jobId: envelope.hop_id },
      );
    } catch (err) {
      if (err instanceof QueueCapacityError) {
        console.warn(`[hop] queue capacity exceeded for ${envelope.hop_id} — falling through`);
      } else {
        console.warn(`[hop] dispatch error for ${envelope.hop_id}:`, err);
      }
      // Both errors are non-fatal — request proceeds regardless
    }
  } else {
    // sync — broadcast directly
    hopBroadcaster.broadcast(`hop.${route.destination}`, event);
  }
}

export function hopMiddleware(req: Request, res: Response, next: NextFunction): void {
  // Only intercept POST /hooks/user-prompt
  if (req.method !== "POST" || !req.path.endsWith("/user-prompt")) {
    return next();
  }

  const body = req.body ?? {};
  const intentTag: string = body.metadata?.intent_tag ?? "";

  // OPT-IN CONTRACT: only activate when source explicitly sets metadata.intent_tag.
  // Normal Claude Code prompts will NOT have this field — they pass through untouched.
  // This prevents Hop from running on every single user-prompt request.
  if (!intentTag) {
    return next();
  }

  const start = Date.now();
  const hop_id = randomUUID();
  const prompt: string = body.prompt ?? "";
  const sourceSkill: string = body.metadata?.source_skill ?? "";
  const sessionId: string = body.sessionId ?? "";

  const envelope: HopEnvelope = {
    hop_id,
    source_skill: sourceSkill || undefined,
    payload: prompt,
    intent_tag: intentTag,
    session_id: sessionId || undefined,
    timestamp: new Date().toISOString(),
    // Confidence: 0.8 when intent explicitly declared, lower for catchall scenarios
    confidence: 0.8,
    dead_lettered: false,
    metadata: { session_id: sessionId },
  };

  try {
    const route = resolveRoute(envelope);

    if (!route) {
      // Dead-letter: no matching rule — log and fall through to gen/ default handling
      envelope.dead_lettered = true;
      writeHopAudit({
        hop_id,
        source_skill: envelope.source_skill,
        route_method: "dead-letter",
        confidence: envelope.confidence,
        dead_lettered: true,
        timestamp: envelope.timestamp,
        duration_ms: Date.now() - start,
        sessionId: sessionId || undefined,
      });
      return next();
    }

    envelope.route = route;

    req.hopDispatchContext = {
      hop_id,
      rule_id: route.rule_id,
      destination: route.destination,
      dispatch_mode: route.dispatch_mode,
    };

    // Apply prompt rewrite template if defined
    if (route.prompt_rewrite_template) {
      const rewritten = route.prompt_rewrite_template
        .replace("{{destination}}", route.destination)
        .replace("{{payload}}", prompt);
      envelope.payload = rewritten;
      req.body = { ...body, prompt: rewritten };
    }

    // Dispatch — async fire-and-forget; never await in the request path
    if (route.destination_type === "local") {
      dispatchLocal(route, envelope).catch((err) => {
        console.warn(`[hop] unhandled dispatchLocal error for ${hop_id}:`, err);
      });
    } else if (route.destination_type === "remote_mcp") {
      dispatchRemoteMcp(route, envelope).catch((err) => {
        console.warn(`[hop] unhandled dispatchRemoteMcp error for ${hop_id}:`, err);
      });
    }

    writeHopAudit({
      hop_id,
      source_skill: envelope.source_skill,
      destination: route.destination,
      route_method: route.rule_id,
      confidence: envelope.confidence,
      dead_lettered: false,
      timestamp: envelope.timestamp,
      duration_ms: Date.now() - start,
      sessionId: sessionId || undefined,
    });
  } catch (err) {
    // SAFETY NET: any unexpected error must still call next()
    // Gen is the only enforcement layer — we must never block a request
    console.error("[hop] unexpected middleware error — falling through:", err);
  }

  return next();
}
