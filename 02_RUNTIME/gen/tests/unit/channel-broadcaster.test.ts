import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { ChannelBroadcaster } from "../../src/channels/channel-broadcaster";
import type { ChannelEvent } from "../../src/channels/channel-types";
import type { Response } from "express";

function mockResponse(): Response {
  return {
    write: vi.fn(),
    end: vi.fn(),
    setHeader: vi.fn(),
    flushHeaders: vi.fn(),
  } as unknown as Response;
}

function makeEvent(
  channelId: string,
  eventType = "test_event"
): ChannelEvent {
  return {
    id: "evt-" + Math.random().toString(36).slice(2),
    channelId,
    eventType,
    payload: { test: true },
    sentAt: new Date().toISOString(),
    source: "internal",
  };
}

describe("ChannelBroadcaster", () => {
  let bc: ChannelBroadcaster;

  beforeEach(() => {
    bc = new ChannelBroadcaster();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("subscribe", () => {
    it("adds a subscriber", () => {
      const res = mockResponse();
      bc.subscribe("session-1", "chan-a", [], res);
      expect(bc.getActiveSubscribers()).toHaveLength(1);
    });

    it("stores correct subscriber metadata", () => {
      const res = mockResponse();
      bc.subscribe("session-1", "chan-a", ["push", "pr"], res);
      const subs = bc.getActiveSubscribers();
      expect(subs[0].sessionId).toBe("session-1");
      expect(subs[0].channelId).toBe("chan-a");
      expect(subs[0].filters).toEqual(["push", "pr"]);
    });

    it("overwrites existing subscription for same sessionId", () => {
      const res1 = mockResponse();
      const res2 = mockResponse();
      bc.subscribe("session-1", "chan-a", [], res1);
      bc.subscribe("session-1", "chan-b", [], res2);
      expect(bc.getActiveSubscribers()).toHaveLength(1);
      expect(bc.getActiveSubscribers()[0].channelId).toBe("chan-b");
    });
  });

  describe("unsubscribe", () => {
    it("removes subscriber by sessionId", () => {
      const res = mockResponse();
      bc.subscribe("session-1", "chan-a", [], res);
      bc.unsubscribe("session-1");
      expect(bc.getActiveSubscribers()).toHaveLength(0);
    });

    it("is a no-op for unknown sessionId", () => {
      expect(() => bc.unsubscribe("nonexistent")).not.toThrow();
    });

    it("removes only the target subscriber when multiple exist", () => {
      bc.subscribe("session-1", "chan-a", [], mockResponse());
      bc.subscribe("session-2", "chan-a", [], mockResponse());
      bc.unsubscribe("session-1");
      const subs = bc.getActiveSubscribers();
      expect(subs).toHaveLength(1);
      expect(subs[0].sessionId).toBe("session-2");
    });
  });

  describe("getActiveSubscribers", () => {
    it("returns empty array when no subscribers", () => {
      expect(bc.getActiveSubscribers()).toHaveLength(0);
    });

    it("returns all current subscribers", () => {
      bc.subscribe("s1", "chan-a", [], mockResponse());
      bc.subscribe("s2", "chan-b", [], mockResponse());
      bc.subscribe("s3", "chan-c", [], mockResponse());
      expect(bc.getActiveSubscribers()).toHaveLength(3);
    });
  });

  describe("broadcast", () => {
    it("sends to subscribers on matching channelId", () => {
      const res1 = mockResponse();
      const res2 = mockResponse();
      bc.subscribe("s1", "chan-a", [], res1);
      bc.subscribe("s2", "chan-b", [], res2);

      const event = makeEvent("chan-a");
      bc.broadcast("chan-a", event);

      expect(res1.write).toHaveBeenCalledOnce();
      expect(res2.write).not.toHaveBeenCalled();
    });

    it("does not send to subscribers on different channelId", () => {
      const res = mockResponse();
      bc.subscribe("s1", "chan-b", [], res);
      bc.broadcast("chan-a", makeEvent("chan-a"));
      expect(res.write).not.toHaveBeenCalled();
    });

    it("applies event type filter — passes matching filter", () => {
      const res = mockResponse();
      bc.subscribe("s1", "chan-a", ["push"], res);
      bc.broadcast("chan-a", makeEvent("chan-a", "push"));
      expect(res.write).toHaveBeenCalledOnce();
    });

    it("applies event type filter — blocks non-matching filter", () => {
      const res = mockResponse();
      bc.subscribe("s1", "chan-a", ["push"], res);
      bc.broadcast("chan-a", makeEvent("chan-a", "pr_opened"));
      expect(res.write).not.toHaveBeenCalled();
    });

    it("no filter means receive all event types", () => {
      const res = mockResponse();
      bc.subscribe("s1", "chan-a", [], res);
      bc.broadcast("chan-a", makeEvent("chan-a", "pr_opened"));
      bc.broadcast("chan-a", makeEvent("chan-a", "push"));
      expect(res.write).toHaveBeenCalledTimes(2);
    });

    it("writes correct SSE format", () => {
      const res = mockResponse();
      bc.subscribe("s1", "chan-a", [], res);
      const event = makeEvent("chan-a");
      bc.broadcast("chan-a", event);

      const written = (res.write as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
      expect(written).toMatch(/^data: /);
      expect(written).toMatch(/\n\n$/);
      const json = JSON.parse(written.slice("data: ".length).trimEnd());
      expect(json.id).toBe(event.id);
      expect(json.eventType).toBe(event.eventType);
    });
  });

  describe("broadcastAll", () => {
    it("sends to all subscribers regardless of channelId", () => {
      const res1 = mockResponse();
      const res2 = mockResponse();
      bc.subscribe("s1", "chan-a", [], res1);
      bc.subscribe("s2", "chan-b", [], res2);

      bc.broadcastAll(makeEvent("chan-a"));

      expect(res1.write).toHaveBeenCalledOnce();
      expect(res2.write).toHaveBeenCalledOnce();
    });
  });

  describe("pruneStale", () => {
    it("removes subscribers whose lastHeartbeatAt is older than maxAgeMs", () => {
      const res = mockResponse();
      bc.subscribe("s1", "chan-a", [], res);

      // Travel time forward: mock Date.now to be 10 minutes ahead
      const realNow = Date.now();
      vi.spyOn(Date, "now").mockReturnValue(realNow + 10 * 60 * 1000);

      bc.pruneStale(5 * 60 * 1000); // 5 min max age
      expect(bc.getActiveSubscribers()).toHaveLength(0);
    });

    it("keeps fresh subscribers", () => {
      const res = mockResponse();
      bc.subscribe("s1", "chan-a", [], res);

      // Only 1 minute has passed — under 5 min threshold
      const realNow = Date.now();
      vi.spyOn(Date, "now").mockReturnValue(realNow + 60 * 1000);

      bc.pruneStale(5 * 60 * 1000);
      expect(bc.getActiveSubscribers()).toHaveLength(1);
    });

    it("prunes stale and keeps fresh in same pass", () => {
      const res1 = mockResponse();
      const res2 = mockResponse();

      // Subscribe s1 with an old timestamp
      bc.subscribe("s1", "chan-a", [], res1);
      // Manually backdate s1's heartbeat
      const subs = bc.getActiveSubscribers();
      subs[0].lastHeartbeatAt = new Date(Date.now() - 10 * 60 * 1000).toISOString();

      // Subscribe s2 fresh
      bc.subscribe("s2", "chan-b", [], res2);

      bc.pruneStale(5 * 60 * 1000);

      const remaining = bc.getActiveSubscribers();
      expect(remaining).toHaveLength(1);
      expect(remaining[0].sessionId).toBe("s2");
    });

    it("uses 5 minutes as default maxAgeMs", () => {
      const res = mockResponse();
      bc.subscribe("s1", "chan-a", [], res);

      const realNow = Date.now();
      vi.spyOn(Date, "now").mockReturnValue(realNow + 6 * 60 * 1000); // 6 min

      bc.pruneStale(); // default 5 min
      expect(bc.getActiveSubscribers()).toHaveLength(0);
    });
  });
});
