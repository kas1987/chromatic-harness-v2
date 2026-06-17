/**
 * hop-middleware.test.ts
 *
 * Unit tests for the Hop (Bell Hop) dispatch middleware.
 * All external I/O and side-effect dependencies are mocked — tests do not
 * require gen/ to be running.
 *
 * Architecture note:
 * hop-middleware.ts loads routingRules once at module startup via loadRoutes()
 * and reloads via a 30s setInterval. To inject per-test routing tables we use
 * vi.resetModules() + dynamic import() to get a fresh module instance for each
 * test that needs a specific routing table.
 *
 * The vi.mock() factories must be self-contained (no outer-scope variables) due
 * to Vitest hoisting. We retrieve the mock functions via vi.mocked() after import.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { Request, Response, NextFunction } from "express";

// ---------------------------------------------------------------------------
// Module mocks — factories are hoisted by Vitest; no outer variables allowed.
// ---------------------------------------------------------------------------

vi.mock("fs", () => {
  const readFileSync = vi.fn(() => JSON.stringify({ routing_rules: [] }));
  const appendFileSync = vi.fn();
  const mkdirSync = vi.fn();
  const statSync = vi.fn(() => ({ mtimeMs: 0 }));
  const mod = { readFileSync, appendFileSync, mkdirSync, statSync } as Record<string, unknown>;
  mod.default = mod;
  return mod;
});

vi.mock("../../src/context/delegate-queue.js", () => {
  class QueueCapacityError extends Error {
    maxDepth: number;
    constructor(msg: string, maxDepth = 0) {
      super(msg);
      this.name = "QueueCapacityError";
      this.maxDepth = maxDepth;
    }
  }
  const DelegateQueue = vi.fn().mockImplementation(() => ({
    enqueue: vi.fn().mockResolvedValue(undefined),
  }));
  return { DelegateQueue, QueueCapacityError };
});

vi.mock("../../src/context/provider-capacity.js", () => {
  const ProviderCapacityTracker = vi.fn().mockImplementation(() => ({
    acquire: vi.fn().mockReturnValue(true),
    release: vi.fn(),
    isAtCapacity: vi.fn().mockReturnValue(false),
    getSnapshot: vi.fn().mockReturnValue({}),
  }));
  return { ProviderCapacityTracker };
});

vi.mock("../../src/channels/channel-broadcaster.js", () => {
  const ChannelBroadcaster = vi.fn().mockImplementation(() => ({
    makeChannelEvent: vi.fn().mockReturnValue({}),
    broadcast: vi.fn(),
  }));
  return { ChannelBroadcaster };
});

vi.mock("../../src/utils/hop-audit.js", () => ({
  writeHopAudit: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Static imports — these load the module with the initial empty routing table.
// ---------------------------------------------------------------------------

import fs from "fs";
import { hopMiddleware } from "../../src/middleware/hop-middleware.js";
import { writeHopAudit } from "../../src/utils/hop-audit.js";
import { DelegateQueue, QueueCapacityError } from "../../src/context/delegate-queue.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeReq(overrides: Partial<{
  method: string;
  path: string;
  body: Record<string, unknown>;
}>): Request {
  return {
    method: overrides.method ?? "POST",
    path: overrides.path ?? "/hooks/user-prompt",
    body: overrides.body ?? {},
  } as unknown as Request;
}

function makeRes(): Response {
  return {} as Response;
}

function routesJson(rules: object[]): string {
  return JSON.stringify({ routing_rules: rules });
}

function dispatchRule(overrides: Record<string, unknown> = {}) {
  return {
    rule_id: "test-dispatch-rule",
    priority: 10,
    intent_tag: "dispatch",
    destination: "test-skill",
    destination_type: "local",
    confidence_floor: 0.5,
    dispatch_mode: "async",
    ...overrides,
  };
}

/**
 * Load a fresh copy of hop-middleware with a specific routing table.
 * vi.resetModules() clears the module registry so the next import re-executes
 * the module, calling loadRoutes() with the current readFileSync mock value.
 */
async function loadMiddlewareWithRoutes(rules: object[]): Promise<{
  hopMiddleware: (req: Request, res: Response, next: NextFunction) => void;
  writeHopAudit: ReturnType<typeof vi.fn>;
}> {
  vi.mocked(fs.readFileSync).mockReturnValue(routesJson(rules));
  vi.resetModules();
  const mod = await import("../../src/middleware/hop-middleware.js");
  const auditMod = await import("../../src/utils/hop-audit.js");
  return {
    hopMiddleware: mod.hopMiddleware,
    writeHopAudit: vi.mocked(auditMod.writeHopAudit),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("hopMiddleware", () => {
  let next: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    next = vi.fn();
    vi.mocked(writeHopAudit).mockClear();
    vi.mocked(fs.readFileSync).mockReturnValue(routesJson([]));
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // 1. Non user-prompt path passes through immediately
  it("hopMiddleware_NonUserPromptPath_PassThrough", () => {
    const req = makeReq({ path: "/hooks/pretool" });
    hopMiddleware(req, makeRes(), next as NextFunction);
    expect(next).toHaveBeenCalledOnce();
  });

  // 2. Opt-in contract: empty intent_tag always passes through, no audit written
  it("hopMiddleware_EmptyIntentTag_AlwaysPassThrough", () => {
    const req = makeReq({
      body: { prompt: "hello", metadata: { intent_tag: "" } },
    });
    hopMiddleware(req, makeRes(), next as NextFunction);
    expect(next).toHaveBeenCalledOnce();
    expect(vi.mocked(writeHopAudit)).not.toHaveBeenCalled();
  });

  // 3. dispatch intent with matching rule routes to destination, audit written
  it("hopMiddleware_DispatchIntent_MatchesRule", async () => {
    const { hopMiddleware: mw, writeHopAudit: audit } = await loadMiddlewareWithRoutes([
      dispatchRule({ intent_tag: "dispatch" }),
    ]);
    const req = makeReq({
      body: {
        prompt: "generate image",
        metadata: { intent_tag: "dispatch", source_skill: "nsfw" },
        sessionId: "sess-1",
      },
    });
    mw(req, makeRes(), next as NextFunction);
    expect(next).toHaveBeenCalledOnce();
    expect(audit).toHaveBeenCalledOnce();
    const auditCall = audit.mock.calls[0][0];
    expect(auditCall.dead_lettered).toBe(false);
    expect(auditCall.destination).toBe("test-skill");
  });

  // 4. No matching rule → dead-lettered=true, next() called
  it("hopMiddleware_DeadLetter_NoMatchingRule", () => {
    // Static import loads with empty routing table (no rules)
    const req = makeReq({
      body: {
        prompt: "some task",
        metadata: { intent_tag: "dispatch" },
      },
    });
    hopMiddleware(req, makeRes(), next as NextFunction);
    expect(next).toHaveBeenCalledOnce();
    expect(vi.mocked(writeHopAudit)).toHaveBeenCalledOnce();
    const auditCall = vi.mocked(writeHopAudit).mock.calls[0][0];
    expect(auditCall.dead_lettered).toBe(true);
    expect(auditCall.route_method).toBe("dead-letter");
  });

  // 5. Confidence below rule floor → rule skipped → dead-lettered
  it("hopMiddleware_ConfidenceBelowFloor_SkipsRule", async () => {
    // Envelope confidence is hardcoded to 0.8; set floor at 0.9 to force skip
    const { hopMiddleware: mw, writeHopAudit: audit } = await loadMiddlewareWithRoutes([
      dispatchRule({ confidence_floor: 0.9, intent_tag: "dispatch" }),
    ]);
    const req = makeReq({
      body: {
        prompt: "generate image",
        metadata: { intent_tag: "dispatch" },
      },
    });
    mw(req, makeRes(), next as NextFunction);
    expect(next).toHaveBeenCalledOnce();
    const auditCall = audit.mock.calls[0][0];
    expect(auditCall.dead_lettered).toBe(true);
  });

  // 6. Priority ordering: lower priority number wins (first match wins)
  it("hopMiddleware_PriorityOrder_FirstMatchWins", async () => {
    const { hopMiddleware: mw, writeHopAudit: audit } = await loadMiddlewareWithRoutes([
      // Inject in reverse order — loadRoutes sorts by priority ascending
      dispatchRule({ rule_id: "low-prio", priority: 50, intent_tag: "dispatch", destination: "skill-b" }),
      dispatchRule({ rule_id: "high-prio", priority: 5, intent_tag: "dispatch", destination: "skill-a" }),
    ]);
    const req = makeReq({
      body: {
        prompt: "route me",
        metadata: { intent_tag: "dispatch" },
      },
    });
    mw(req, makeRes(), next as NextFunction);
    expect(next).toHaveBeenCalledOnce();
    const auditCall = audit.mock.calls[0][0];
    // Priority 5 < 50, so skill-a (high-prio rule) wins
    expect(auditCall.destination).toBe("skill-a");
    expect(auditCall.route_method).toBe("high-prio");
  });

  // 7. prompt_rewrite_template substitutes {{destination}} and {{payload}}
  it("hopMiddleware_PromptRewrite_AppliesTemplate", async () => {
    const { hopMiddleware: mw } = await loadMiddlewareWithRoutes([
      dispatchRule({
        intent_tag: "dispatch",
        destination: "knowledge",
        prompt_rewrite_template: "Execute via {{destination}}: {{payload}}",
      }),
    ]);
    const req = makeReq({
      body: {
        prompt: "find the answer",
        metadata: { intent_tag: "dispatch" },
      },
    });
    mw(req, makeRes(), next as NextFunction);
    expect(next).toHaveBeenCalledOnce();
    expect(req.body.prompt).toBe("Execute via knowledge: find the answer");
  });

  // 8. Successful dispatch writes audit with correct fields
  it("hopMiddleware_AuditLog_Written", async () => {
    const { hopMiddleware: mw, writeHopAudit: audit } = await loadMiddlewareWithRoutes([
      dispatchRule({ intent_tag: "dispatch", destination: "comfyui-workflow-steward" }),
    ]);
    const req = makeReq({
      body: {
        prompt: "generate",
        metadata: { intent_tag: "dispatch" },
        sessionId: "audit-sess",
      },
    });
    mw(req, makeRes(), next as NextFunction);
    expect(audit).toHaveBeenCalledOnce();
    const entry = audit.mock.calls[0][0];
    expect(entry.hop_id).toBeDefined();
    expect(entry.dead_lettered).toBe(false);
    expect(entry.destination).toBe("comfyui-workflow-steward");
    expect(typeof entry.duration_ms).toBe("number");
  });

  // 9. Dead-letter path also writes audit entry
  it("hopMiddleware_AuditLog_DeadLetter_Written", () => {
    const req = makeReq({
      body: {
        prompt: "no match",
        metadata: { intent_tag: "trigger" },
      },
    });
    hopMiddleware(req, makeRes(), next as NextFunction);
    expect(vi.mocked(writeHopAudit)).toHaveBeenCalledOnce();
    const entry = vi.mocked(writeHopAudit).mock.calls[0][0];
    expect(entry.dead_lettered).toBe(true);
    expect(entry.route_method).toBe("dead-letter");
    expect(entry.hop_id).toBeDefined();
  });

  // 10. Invalid regex in rule → rule skipped gracefully, falls to dead-letter
  it("hopMiddleware_InvalidRegex_SkipsRule", async () => {
    const { hopMiddleware: mw, writeHopAudit: audit } = await loadMiddlewareWithRoutes([
      dispatchRule({
        intent_tag: "dispatch",
        payload_pattern: "[invalid(regex", // malformed — missing closing bracket/paren
      }),
    ]);
    const req = makeReq({
      body: {
        prompt: "generate something",
        metadata: { intent_tag: "dispatch" },
      },
    });
    expect(() => mw(req, makeRes(), next as NextFunction)).not.toThrow();
    expect(next).toHaveBeenCalledOnce();
    // Rule was skipped due to invalid regex → falls to dead-letter
    const auditCall = audit.mock.calls[0][0];
    expect(auditCall.dead_lettered).toBe(true);
  });

  // 11. QueueCapacityError from enqueue → falls through, next() still called
  it("hopMiddleware_QueueCapacity_FallsThrough", async () => {
    const { hopMiddleware: mw } = await loadMiddlewareWithRoutes([
      dispatchRule({ intent_tag: "dispatch", destination_type: "local", dispatch_mode: "async" }),
    ]);

    // The most recently constructed DelegateQueue instance is the hopQueue from the freshly
    // loaded module. Make its enqueue method throw QueueCapacityError.
    const instances = vi.mocked(DelegateQueue).mock.instances;
    const hopQueueInstance = instances[instances.length - 1] as { enqueue: ReturnType<typeof vi.fn> } | undefined;
    if (hopQueueInstance?.enqueue) {
      vi.spyOn(hopQueueInstance, "enqueue").mockRejectedValue(
        new QueueCapacityError("queue full", 50),
      );
    }

    const req = makeReq({
      body: {
        prompt: "capacity test",
        metadata: { intent_tag: "dispatch" },
      },
    });

    mw(req, makeRes(), next as NextFunction);
    // dispatchLocal is fire-and-forget — allow the rejected promise to settle
    await Promise.resolve();
    await Promise.resolve();

    expect(next).toHaveBeenCalledOnce();
  });

  // 12. Malformed JSON in routes file → empty rules, no crash
  it("hopMiddleware_LoadRoutes_InvalidJson_ReturnsEmpty", async () => {
    // loadRoutes() catches JSON.parse errors and returns []
    vi.mocked(fs.readFileSync).mockReturnValue("NOT { valid JSON");
    vi.resetModules();
    const mod = await import("../../src/middleware/hop-middleware.js");
    const auditMod = await import("../../src/utils/hop-audit.js");
    const auditFn = vi.mocked(auditMod.writeHopAudit);

    const req = makeReq({
      body: {
        prompt: "any prompt",
        metadata: { intent_tag: "dispatch" },
      },
    });

    expect(() => mod.hopMiddleware(req, makeRes(), next as NextFunction)).not.toThrow();
    expect(next).toHaveBeenCalledOnce();
    // Empty routing table → dead-letter audit
    const auditCall = auditFn.mock.calls[0][0];
    expect(auditCall.dead_lettered).toBe(true);
  });

  // 13. Matched route sets req.hopDispatchContext for hooks downstream
  it("hopMiddleware_SetsHopDispatchContextOnRequest", async () => {
    const { hopMiddleware: mw } = await loadMiddlewareWithRoutes([
      dispatchRule({ intent_tag: "dispatch", destination: "inbox" }),
    ]);
    const req = makeReq({
      body: {
        prompt: "dispatch me",
        metadata: { intent_tag: "dispatch" },
        sessionId: "s-ctx",
      },
    });
    mw(req, makeRes(), next as NextFunction);
    expect(req.hopDispatchContext).toBeDefined();
    expect(req.hopDispatchContext?.destination).toBe("inbox");
    expect(req.hopDispatchContext?.rule_id).toBe("test-dispatch-rule");
    expect(req.hopDispatchContext?.hop_id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );
  });

  // 14. initializeHopBroadcaster wires broadcast to the shared instance
  it("hopMiddleware_SharedBroadcaster_ReceivesBroadcast", async () => {
    const shared = {
      makeChannelEvent: vi.fn().mockReturnValue({ id: "evt-1" }),
      broadcast: vi.fn(),
    };
    vi.mocked(fs.readFileSync).mockReturnValue(
      routesJson([dispatchRule({ intent_tag: "dispatch", dispatch_mode: "sync" })]),
    );
    vi.resetModules();
    const mod = await import("../../src/middleware/hop-middleware.js");
    mod.initializeHopBroadcaster(shared as never);
    const req = makeReq({
      body: {
        prompt: "sync dispatch",
        metadata: { intent_tag: "dispatch" },
      },
    });
    mod.hopMiddleware(req, makeRes(), next as NextFunction);
    expect(shared.makeChannelEvent).toHaveBeenCalled();
    expect(shared.broadcast).toHaveBeenCalled();
  });

  // 15. Even on unexpected error, next() is always called (safety net)
  it("hopMiddleware_AlwaysCallsNext", () => {
    // Force writeHopAudit to throw — the outer try/catch must still call next()
    vi.mocked(writeHopAudit).mockImplementationOnce(() => {
      throw new Error("unexpected audit failure");
    });

    // Static instance has empty routing table → dead-letter path → writeHopAudit called → throws
    const req = makeReq({
      body: {
        prompt: "any",
        metadata: { intent_tag: "dispatch" },
      },
    });

    expect(() => hopMiddleware(req, makeRes(), next as NextFunction)).not.toThrow();
    expect(next).toHaveBeenCalledOnce();
  });
});
