import { describe, it, expect, beforeEach } from "vitest";
import Database from "better-sqlite3";
import {
  ModelPerformanceTracker,
  type ModelPerformanceRecord,
} from "../../src/learning/model-performance-tracker.js";
import type { LlmProvider } from "../../src/llm/llm-types.js";

function makeTracker(): ModelPerformanceTracker {
  const db = new Database(":memory:");
  return new ModelPerformanceTracker(db);
}

// Helper: record N successes for a given model/intent/scope
function recordSuccesses(
  tracker: ModelPerformanceTracker,
  model: LlmProvider,
  intent: string,
  scope: string,
  count: number,
  latencyMs = 100,
  costUsd = 0.001,
): void {
  for (let i = 0; i < count; i++) {
    tracker.record(model, intent, scope, "success", latencyMs, costUsd);
  }
}

function recordFailures(
  tracker: ModelPerformanceTracker,
  model: LlmProvider,
  intent: string,
  scope: string,
  count: number,
): void {
  for (let i = 0; i < count; i++) {
    tracker.record(model, intent, scope, "failure", 0, 0);
  }
}

// ---------------------------------------------------------------------------
// TC-1: InsufficientData → null
// ---------------------------------------------------------------------------

describe("ModelPerformanceTracker.getBestModel", () => {
  it("TC-1: returns null when no rows exist for intent/scope", () => {
    const tracker = makeTracker();
    const result = tracker.getBestModel("code", "simple");
    expect(result).toBeNull();
  });

  it("TC-1b: returns null when success_count < 5 for all rows", () => {
    const tracker = makeTracker();
    recordSuccesses(tracker, "claude", "code", "simple", 4);
    const result = tracker.getBestModel("code", "simple");
    expect(result).toBeNull();
  });

  // -------------------------------------------------------------------------
  // TC-2: SufficientData → bestModel
  // -------------------------------------------------------------------------

  it("TC-2: returns model with highest success rate when both meet threshold", () => {
    const tracker = makeTracker();
    // claude: 6 successes + 1 failure = 85.7% success rate
    recordSuccesses(tracker, "claude", "code", "simple", 6);
    recordFailures(tracker, "claude", "code", "simple", 1);
    // gpt: 5 successes + 3 failures = 62.5% success rate
    recordSuccesses(tracker, "gpt", "code", "simple", 5);
    recordFailures(tracker, "gpt", "code", "simple", 3);

    const result = tracker.getBestModel("code", "simple");
    expect(result).toBe("claude");
  });

  // -------------------------------------------------------------------------
  // TC-3: Record → upsert (no duplicate rows)
  // -------------------------------------------------------------------------

  it("TC-3: record() uses upsert — exactly one row per (model, intent, scope)", () => {
    const tracker = makeTracker();
    tracker.record("claude", "code", "simple", "success", 300, 0.003);
    tracker.record("claude", "code", "simple", "success", 300, 0.003);

    const stats = tracker.getStats();
    const rows = stats.filter(
      (r) => r.model === "claude" && r.intent === "code" && r.scope === "simple",
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].successCount).toBe(2);
    expect(rows[0].avgLatencyMs).toBeCloseTo(300, 1);
  });

  // -------------------------------------------------------------------------
  // TC-4: TieBreaking → higher success rate
  // -------------------------------------------------------------------------

  it("TC-4: returns model with higher success rate when counts are equal", () => {
    const tracker = makeTracker();
    // claude: 5 successes + 5 failures = 50%
    recordSuccesses(tracker, "claude", "manage", "medium", 5);
    recordFailures(tracker, "claude", "manage", "medium", 5);
    // gpt: 5 successes + 0 failures = 100%
    recordSuccesses(tracker, "gpt", "manage", "medium", 5);

    const result = tracker.getBestModel("manage", "medium");
    expect(result).toBe("gpt");
  });

  // -------------------------------------------------------------------------
  // TC-5: Below-threshold row ignored even when other row qualifies
  // -------------------------------------------------------------------------

  it("TC-5: excludes model with success_count < 5 even at 100% rate", () => {
    const tracker = makeTracker();
    // gemini: 3 successes only (100% but < 5 samples)
    recordSuccesses(tracker, "gemini", "explore", "simple", 3);
    // claude: 5 successes + 2 failures = 71.4%
    recordSuccesses(tracker, "claude", "explore", "simple", 5);
    recordFailures(tracker, "claude", "explore", "simple", 2);

    const result = tracker.getBestModel("explore", "simple");
    expect(result).toBe("claude");
  });

  // -------------------------------------------------------------------------
  // TC-6: record() incremental running average
  // -------------------------------------------------------------------------

  it("TC-6: avgLatencyMs and avgCostUsd are computed with running-average formula", () => {
    const tracker = makeTracker();
    tracker.record("claude", "code", "simple", "success", 100, 0.001);
    tracker.record("claude", "code", "simple", "success", 300, 0.003);

    const stats = tracker.getStats();
    const row = stats.find(
      (r) => r.model === "claude" && r.intent === "code" && r.scope === "simple",
    );
    expect(row).toBeDefined();
    expect(row!.avgLatencyMs).toBeCloseTo(200, 1);
    expect(row!.avgCostUsd).toBeCloseTo(0.002, 4);
  });

  // -------------------------------------------------------------------------
  // TC-7: getStats() returns camelCase ModelPerformanceRecord[]
  // -------------------------------------------------------------------------

  it("TC-7: getStats() returns camelCase fields and covers all rows", () => {
    const tracker = makeTracker();
    recordSuccesses(tracker, "claude", "code", "simple", 1);
    recordSuccesses(tracker, "gpt", "explore", "medium", 1);

    const stats: ModelPerformanceRecord[] = tracker.getStats();
    expect(stats).toHaveLength(2);

    for (const row of stats) {
      // camelCase field presence (TypeScript compile would catch missing fields,
      // but we also verify at runtime that the shape is correct)
      expect(typeof row.model).toBe("string");
      expect(typeof row.intent).toBe("string");
      expect(typeof row.scope).toBe("string");
      expect(typeof row.successCount).toBe("number");
      expect(typeof row.failureCount).toBe("number");
      expect(typeof row.avgLatencyMs).toBe("number");
      expect(typeof row.avgCostUsd).toBe("number");
      // snake_case must NOT leak out
      expect((row as Record<string, unknown>)["success_count"]).toBeUndefined();
      expect((row as Record<string, unknown>)["failure_count"]).toBeUndefined();
      expect((row as Record<string, unknown>)["avg_latency_ms"]).toBeUndefined();
      expect((row as Record<string, unknown>)["avg_cost_usd"]).toBeUndefined();
    }
  });

  // -------------------------------------------------------------------------
  // AllModels: all LlmProvider values accepted without error
  // -------------------------------------------------------------------------

  it("accepts all LlmProvider values without error", () => {
    const tracker = makeTracker();
    const providers: LlmProvider[] = ["claude", "gpt", "gemini", "ollama", "lm-studio", "minimax", "gemma"];
    for (const model of providers) {
      expect(() =>
        tracker.record(model, "code", "simple", "success", 100, 0.001),
      ).not.toThrow();
    }
    const stats = tracker.getStats();
    expect(stats).toHaveLength(providers.length);
  });

  // -------------------------------------------------------------------------
  // Scope isolation: getBestModel does not mix across different scopes
  // -------------------------------------------------------------------------

  it("getBestModel isolates by scope — data in 'complex' does not affect 'simple'", () => {
    const tracker = makeTracker();
    recordSuccesses(tracker, "gpt", "code", "complex", 6);
    // Only "complex" has data; "simple" should return null
    const result = tracker.getBestModel("code", "simple");
    expect(result).toBeNull();
  });
});
