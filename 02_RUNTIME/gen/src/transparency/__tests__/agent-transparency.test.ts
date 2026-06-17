import { describe, it, expect, beforeEach } from "vitest";
import { AgentTransparencyService } from "../agent-transparency.js";

function makeService(): AgentTransparencyService {
  return new AgentTransparencyService();
}

describe("AgentTransparencyService.recordDrift", () => {
  it("captures a drift event", () => {
    const svc = makeService();
    svc.recordDrift("minimax", "claude", "explore", "minimax unavailable");
    const alerts = svc.getRecentDrift();
    expect(alerts).toHaveLength(1);
    expect(alerts[0].suggested).toBe("minimax");
    expect(alerts[0].actual).toBe("claude");
    expect(alerts[0].intent).toBe("explore");
    expect(alerts[0].reason).toBe("minimax unavailable");
  });

  it("most recent drift event appears first (prepend order)", () => {
    const svc = makeService();
    svc.recordDrift("a", "b", "code", "reason1");
    svc.recordDrift("c", "d", "explore", "reason2");
    const alerts = svc.getRecentDrift();
    expect(alerts[0].reason).toBe("reason2"); // most recent first
    expect(alerts[1].reason).toBe("reason1");
  });

  it("caps drift log at 20 entries", () => {
    const svc = makeService();
    for (let i = 0; i < 25; i++) {
      svc.recordDrift("a", "b", "code", `reason-${i}`);
    }
    expect(svc.getRecentDrift()).toHaveLength(20);
  });

  it("drift events include ISO-8601 timestamp", () => {
    const svc = makeService();
    svc.recordDrift("ollama", "claude", "manage", "test");
    const [event] = svc.getRecentDrift();
    expect(() => new Date(event.timestamp)).not.toThrow();
    expect(new Date(event.timestamp).toISOString()).toBe(event.timestamp);
  });
});

describe("AgentTransparencyService.buildSnapshot", () => {
  it("includes drift alerts (last 5) in snapshot", () => {
    const svc = makeService();
    for (let i = 0; i < 8; i++) {
      svc.recordDrift("a", "b", "code", `reason-${i}`);
    }
    const snap = svc.buildSnapshot("claude", 0.9);
    expect(snap.driftAlerts).toHaveLength(5); // capped at 5 in snapshot
  });

  it("snapshot.generatedAt is valid ISO-8601", () => {
    const svc = makeService();
    const snap = svc.buildSnapshot("ollama", 1.0, ["task A"]);
    expect(() => new Date(snap.generatedAt)).not.toThrow();
    expect(new Date(snap.generatedAt).toISOString()).toBe(snap.generatedAt);
  });

  it("snapshot reflects activeLlm and routingConfidence", () => {
    const svc = makeService();
    const snap = svc.buildSnapshot("minimax", 0.72, ["task X"]);
    expect(snap.activeLlm).toBe("minimax");
    expect(snap.routingConfidence).toBe(0.72);
    expect(snap.activeTasks).toEqual(["task X"]);
  });

  it("upcomingWork defaults to empty (populated externally by route handler)", () => {
    const svc = makeService();
    const snap = svc.buildSnapshot("claude", 1.0);
    expect(snap.upcomingWork).toEqual([]);
  });
});

describe("AgentTransparencyService.getDriftRate", () => {
  it("returns 0 when no drift recorded", () => {
    expect(makeService().getDriftRate()).toBe(0);
  });

  it("returns non-zero after drift events", () => {
    const svc = makeService();
    svc.recordDrift("a", "b", "code", "r1");
    svc.recordDrift("a", "b", "code", "r2");
    expect(svc.getDriftRate()).toBeGreaterThan(0);
  });
});

describe("AgentTransparencyService.clearDrift", () => {
  it("empties the drift log", () => {
    const svc = makeService();
    svc.recordDrift("a", "b", "code", "r");
    svc.clearDrift();
    expect(svc.getRecentDrift()).toHaveLength(0);
    expect(svc.getDriftRate()).toBe(0);
  });
});
