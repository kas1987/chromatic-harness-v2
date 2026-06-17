import { describe, it, expect, beforeEach } from "vitest";
import { NudgeTracker } from "../../src/core/nudge-tracker";

describe("NudgeTracker", () => {
  let tracker: NudgeTracker;

  beforeEach(() => {
    tracker = new NudgeTracker({ interval: 3, ttlMs: 60_000 });
  });

  it("returns false for first N-1 prompts in a session", () => {
    expect(tracker.tick("session-a")).toBe(false); // count=1
    expect(tracker.tick("session-a")).toBe(false); // count=2
  });

  it("returns true on the Nth prompt", () => {
    tracker.tick("session-a"); // 1
    tracker.tick("session-a"); // 2
    expect(tracker.tick("session-a")).toBe(true); // 3 — trigger
  });

  it("resets after trigger — next cycle starts fresh", () => {
    tracker.tick("session-a"); // 1
    tracker.tick("session-a"); // 2
    tracker.tick("session-a"); // 3 — trigger, resets to 0
    expect(tracker.tick("session-a")).toBe(false); // 1 again
    expect(tracker.tick("session-a")).toBe(false); // 2
    expect(tracker.tick("session-a")).toBe(true);  // 3 — trigger again
  });

  it("tracks sessions independently", () => {
    tracker.tick("session-a"); // a=1
    tracker.tick("session-a"); // a=2
    tracker.tick("session-b"); // b=1
    expect(tracker.tick("session-a")).toBe(true);  // a=3 triggers
    expect(tracker.tick("session-b")).toBe(false); // b=2
  });

  it("returns false when interval is 0 (disabled)", () => {
    const disabled = new NudgeTracker({ interval: 0, ttlMs: 60_000 });
    expect(disabled.tick("s")).toBe(false);
    expect(disabled.tick("s")).toBe(false);
    expect(disabled.tick("s")).toBe(false);
  });

  it("getStats returns tracked session count", () => {
    tracker.tick("s1");
    tracker.tick("s2");
    expect(tracker.getStats().tracked).toBe(2);
  });
});
