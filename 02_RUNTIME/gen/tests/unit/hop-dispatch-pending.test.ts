import { describe, it, expect, beforeEach } from "vitest";
import { hopDispatchPendingStore } from "../../src/routing/hop-dispatch-pending.js";

describe("hopDispatchPendingStore", () => {
  beforeEach(() => {
    hopDispatchPendingStore.drain("sess-a");
    hopDispatchPendingStore.drain("sess-b");
  });

  it("drain_returnsEmpty_whenNothingQueued", () => {
    expect(hopDispatchPendingStore.drain("sess-a")).toEqual([]);
  });

  it("enqueue_then_drain_returnsLines_andClears", () => {
    hopDispatchPendingStore.enqueue("sess-a", "hop_id=1 status=ok");
    hopDispatchPendingStore.enqueue("sess-a", "hop_id=2 status=fail summary=oops");
    const lines = hopDispatchPendingStore.drain("sess-a");
    expect(lines).toHaveLength(2);
    expect(lines[0]).toContain("hop_id=1");
    expect(hopDispatchPendingStore.drain("sess-a")).toEqual([]);
  });

  it("sessionsStayIsolated", () => {
    hopDispatchPendingStore.enqueue("sess-a", "a-only");
    hopDispatchPendingStore.enqueue("sess-b", "b-only");
    expect(hopDispatchPendingStore.drain("sess-a")).toEqual(["a-only"]);
    expect(hopDispatchPendingStore.drain("sess-b")).toEqual(["b-only"]);
  });
});
