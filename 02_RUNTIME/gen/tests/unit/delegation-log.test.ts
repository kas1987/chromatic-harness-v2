import { describe, it, expect, beforeEach } from "vitest";
import Database from "better-sqlite3";
import { DelegationLog } from "../../src/context/delegation-log.js";
import type { DelegationRecord } from "../../src/context/delegation-log.js";

function openDb(): Database.Database {
  return new Database(":memory:");
}

function makeEntry(overrides: Partial<Omit<DelegationRecord, "id" | "createdAt">> = {}): Omit<DelegationRecord, "id" | "createdAt"> {
  return {
    traceId: "trace_abc123",
    attemptNumber: 1,
    provider: "gpt",
    model: "gpt-4o",
    promptSent: "Original request: do X. Task: do Y.",
    response: "Here is the result for Y.",
    success: true,
    latencyMs: 420,
    failureReason: null,
    fallbackTriggered: false,
    resolvedBy: null,
    fallbackNote: null,
    ...overrides,
  };
}

describe("DelegationLog.record", () => {
  let log: DelegationLog;

  beforeEach(() => {
    log = new DelegationLog(openDb());
  });

  it("returns a record with generated id and createdAt", () => {
    const rec = log.record(makeEntry());
    expect(rec.id).toMatch(/^dlg_/);
    expect(rec.createdAt).toBeTruthy();
    expect(() => new Date(rec.createdAt)).not.toThrow();
  });

  it("persists all fields correctly", () => {
    const entry = makeEntry({ provider: "gemini", model: "gemini-2.0-flash", latencyMs: 800, success: false, failureReason: "timeout" });
    log.record(entry);
    const [fetched] = log.getByTrace("trace_abc123");
    expect(fetched.provider).toBe("gemini");
    expect(fetched.latencyMs).toBe(800);
    expect(fetched.success).toBe(false);
    expect(fetched.failureReason).toBe("timeout");
  });

  it("records fallback metadata", () => {
    const entry = makeEntry({ fallbackTriggered: true, resolvedBy: "claude", fallbackNote: "Timeout — falling back to Sonnet" });
    log.record(entry);
    const [rec] = log.getByTrace("trace_abc123");
    expect(rec.fallbackTriggered).toBe(true);
    expect(rec.resolvedBy).toBe("claude");
    expect(rec.fallbackNote).toContain("Sonnet");
  });
});

describe("DelegationLog.getByTrace", () => {
  let log: DelegationLog;

  beforeEach(() => {
    log = new DelegationLog(openDb());
  });

  it("returns records in attempt order", () => {
    log.record(makeEntry({ attemptNumber: 2, provider: "gpt" }));
    log.record(makeEntry({ attemptNumber: 1, provider: "gemini" }));
    const recs = log.getByTrace("trace_abc123");
    expect(recs[0].attemptNumber).toBe(1);
    expect(recs[1].attemptNumber).toBe(2);
  });

  it("returns empty array for unknown traceId", () => {
    expect(log.getByTrace("nonexistent")).toHaveLength(0);
  });

  it("only returns records for the requested traceId", () => {
    log.record(makeEntry({ traceId: "trace_abc123" }));
    log.record(makeEntry({ traceId: "trace_xyz789" }));
    const recs = log.getByTrace("trace_abc123");
    expect(recs).toHaveLength(1);
    expect(recs[0].traceId).toBe("trace_abc123");
  });
});

describe("DelegationLog.recentFailures", () => {
  let log: DelegationLog;

  beforeEach(() => {
    log = new DelegationLog(openDb());
  });

  it("returns only failed records", () => {
    log.record(makeEntry({ success: true }));
    log.record(makeEntry({ traceId: "trace2", success: false, failureReason: "timeout" }));
    const failures = log.recentFailures();
    expect(failures.every((r) => !r.success)).toBe(true);
  });
});

describe("DelegationLog.markResolved", () => {
  it("sets resolvedBy on all unresolved records for the trace", () => {
    const log = new DelegationLog(openDb());
    log.record(makeEntry({ attemptNumber: 1, success: false, resolvedBy: null }));
    log.record(makeEntry({ attemptNumber: 2, success: false, resolvedBy: null }));
    log.markResolved("trace_abc123", "claude");

    const recs = log.getByTrace("trace_abc123");
    expect(recs.every((r) => r.resolvedBy === "claude")).toBe(true);
  });
});
