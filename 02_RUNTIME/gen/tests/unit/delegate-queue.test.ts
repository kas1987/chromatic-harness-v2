import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { DelegateQueue, QueueCapacityError, JobTimeoutError } from "../../src/context/delegate-queue.js";
import type { ProviderCapacityTracker } from "../../src/context/provider-capacity.js";

// ---------------------------------------------------------------------------
// Minimal capacity tracker stub — controls slot availability in tests
// ---------------------------------------------------------------------------

function makeCapacity(totalFreeSlots = 10): ProviderCapacityTracker {
  return {
    acquire: vi.fn().mockReturnValue(true),
    release: vi.fn(),
    isAtCapacity: vi.fn().mockReturnValue(false),
    getSnapshot: vi.fn().mockReturnValue({
      claude:      { inFlight: 0, maxSlots: 8, atCapacity: false },
      gemini:      { inFlight: 0, maxSlots: 3, atCapacity: false },
      "lm-studio": { inFlight: 0, maxSlots: 1, atCapacity: false },
      ollama:      { inFlight: 0, maxSlots: 1, atCapacity: false },
      gpt:         { inFlight: 0, maxSlots: Math.max(0, totalFreeSlots - 13), atCapacity: false },
    }),
  } as unknown as ProviderCapacityTracker;
}

function makeFullCapacity(): ProviderCapacityTracker {
  const snapshot = {
    claude:      { inFlight: 8, maxSlots: 8, atCapacity: true },
    gemini:      { inFlight: 3, maxSlots: 3, atCapacity: true },
    "lm-studio": { inFlight: 1, maxSlots: 1, atCapacity: true },
    ollama:      { inFlight: 1, maxSlots: 1, atCapacity: true },
    gpt:         { inFlight: 5, maxSlots: 5, atCapacity: true },
  };
  return {
    acquire: vi.fn().mockReturnValue(false),
    release: vi.fn(),
    isAtCapacity: vi.fn().mockReturnValue(true),
    getSnapshot: vi.fn().mockReturnValue(snapshot),
  } as unknown as ProviderCapacityTracker;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DelegateQueue — basic enqueue + execute", () => {
  let queue: DelegateQueue;

  beforeEach(() => {
    vi.useFakeTimers();
    queue = new DelegateQueue(makeCapacity(), 50, 50);
  });

  afterEach(() => {
    queue.drain("test teardown");
    vi.useRealTimers();
  });

  it("executes a job and resolves with the result", async () => {
    const promise = queue.enqueue(() => Promise.resolve("hello"));
    vi.advanceTimersByTime(100); // tick the poller
    const result = await promise;
    expect(result).toBe("hello");
  });

  it("executes multiple jobs and resolves each independently", async () => {
    const jobs = [
      queue.enqueue(() => Promise.resolve(1)),
      queue.enqueue(() => Promise.resolve(2)),
      queue.enqueue(() => Promise.resolve(3)),
    ];
    vi.advanceTimersByTime(200);
    const results = await Promise.all(jobs);
    expect(results).toEqual([1, 2, 3]);
  });

  it("propagates execution errors to the caller", async () => {
    const promise = queue.enqueue(() => Promise.reject(new Error("provider down")));
    vi.advanceTimersByTime(100);
    await expect(promise).rejects.toThrow("provider down");
  });
});

describe("DelegateQueue — priority ordering", () => {
  let queue: DelegateQueue;
  const executionOrder: string[] = [];

  beforeEach(() => {
    vi.useFakeTimers();
    executionOrder.length = 0;
    // Use large poll interval so we control dispatch timing manually
    queue = new DelegateQueue(makeCapacity(), 50, 5000);
  });

  afterEach(() => {
    queue.drain("test teardown");
    vi.useRealTimers();
  });

  it("dispatches high-priority jobs before normal and low", async () => {
    // Enqueue in reverse priority order — queue should re-sort
    const low    = queue.enqueue(() => { executionOrder.push("low");    return Promise.resolve("low");    }, { priority: "low" });
    const normal = queue.enqueue(() => { executionOrder.push("normal"); return Promise.resolve("normal"); }, { priority: "normal" });
    const high   = queue.enqueue(() => { executionOrder.push("high");   return Promise.resolve("high");   }, { priority: "high" });

    vi.advanceTimersByTime(5100); // tick the poller
    await Promise.all([low, normal, high]);
    expect(executionOrder[0]).toBe("high");
    expect(executionOrder[1]).toBe("normal");
    expect(executionOrder[2]).toBe("low");
  });
});

describe("DelegateQueue — capacity backpressure", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("QueueCapacityError_WhenMaxDepthReached: rejects immediately when queue is full", async () => {
    vi.useFakeTimers();
    const queue = new DelegateQueue(makeFullCapacity(), 2, 50); // max depth = 2

    // Never-resolving jobs to fill the queue — suppress unhandled rejections from drain()
    const neverResolve = () => new Promise<string>(() => {});
    const p1 = queue.enqueue(neverResolve).catch(() => {});
    const p2 = queue.enqueue(neverResolve).catch(() => {});

    // Third job should be rejected immediately
    await expect(queue.enqueue(neverResolve)).rejects.toBeInstanceOf(QueueCapacityError);

    queue.drain("test teardown");
    await Promise.all([p1, p2]);
    vi.useRealTimers();
  });

  it("QueueCapacityError_HasCorrectDepthInfo: error carries depth info", async () => {
    vi.useFakeTimers();
    const queue = new DelegateQueue(makeFullCapacity(), 1, 50);
    const neverResolve = () => new Promise<string>(() => {});
    const p1 = queue.enqueue(neverResolve).catch(() => {});

    try {
      await queue.enqueue(neverResolve);
      expect.fail("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(QueueCapacityError);
      expect((err as QueueCapacityError).maxDepth).toBe(1);
    }

    queue.drain("test teardown");
    await p1;
    vi.useRealTimers();
  });
});

describe("DelegateQueue — timeout", () => {
  it("JobTimeoutError_WhenJobSitsInQueueTooLong: rejects if job never dispatched within timeout", async () => {
    vi.useFakeTimers();
    // Use full-capacity stub — nothing dispatches, job sits in queue
    const queue = new DelegateQueue(makeFullCapacity(), 50, 5000);

    const promise = queue.enqueue(
      () => Promise.resolve("unreachable"),
      { timeoutMs: 500 },
    );

    // Advance past the timeout
    vi.advanceTimersByTime(600);
    await expect(promise).rejects.toBeInstanceOf(JobTimeoutError);

    queue.drain("test teardown");
    vi.useRealTimers();
  });
});

describe("DelegateQueue — stats", () => {
  it("getStats_ReflectsQueueDepthAndInFlight: tracks pending and in-flight counts", async () => {
    vi.useFakeTimers();
    const queue = new DelegateQueue(makeCapacity(), 50, 5000); // large poll so we can inspect before dispatch

    let resolve1!: () => void;
    const job1 = queue.enqueue(() => new Promise<string>((r) => { resolve1 = () => r("done"); }));

    // Before dispatch tick, job is pending
    const statsBefore = queue.getStats();
    expect(statsBefore.pending).toBe(1);
    expect(statsBefore.totalAccepted).toBe(1);

    vi.advanceTimersByTime(5100); // dispatch
    // After dispatch, pending moves to inFlight
    const statsAfter = queue.getStats();
    expect(statsAfter.pending).toBe(0);
    expect(statsAfter.inFlight).toBe(1);

    resolve1();
    await job1;
    const statsDone = queue.getStats();
    expect(statsDone.inFlight).toBe(0);
    expect(statsDone.totalCompleted).toBe(1);

    queue.drain("test teardown");
    vi.useRealTimers();
  });

  it("drain_RejectsAllPendingJobs: drain() rejects all waiting jobs", async () => {
    vi.useFakeTimers();
    const queue = new DelegateQueue(makeFullCapacity(), 50, 5000);

    const p1 = queue.enqueue(() => Promise.resolve("x"), { timeoutMs: 60_000 });
    const p2 = queue.enqueue(() => Promise.resolve("y"), { timeoutMs: 60_000 });

    queue.drain("shutting down");

    await expect(p1).rejects.toThrow("shutting down");
    await expect(p2).rejects.toThrow("shutting down");
    vi.useRealTimers();
  });
});
