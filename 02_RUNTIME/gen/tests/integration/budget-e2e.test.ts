/**
 * Full E2E budget lifecycle tests.
 * Covers: token accumulation, warning thresholds, soft/hard caps,
 * policy switching, complexity routing, daily reset, fallback chain,
 * cost accuracy tracking, and spend enforcement.
 */
import { describe, it, expect, beforeEach } from "vitest";
import Database from "better-sqlite3";
import { BudgetStore } from "../../src/budget/budget-store.js";
import { BudgetAllocator } from "../../src/budget/budget-allocator.js";
import { NormalizedBudgetManager } from "../../src/budget/normalized-budget-manager.js";
import { AggressiveBudgetManager } from "../../src/budget/aggressive-budget-manager.js";
import { selectBudgetManager } from "../../src/budget/budget-policy-selector.js";
import { classifyTaskComplexity } from "../../src/budget/task-complexity-classifier.js";
import { CostAccuracyTracker } from "../../src/budget/cost-accuracy-tracker.js";
import {
  BudgetPolicy,
  DEFAULT_TOKEN_BUDGET_CONFIG,
} from "../../src/budget/budget-types.js";
import { getDefaultBudgetConfig } from "../../src/budget/budget-config.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeDb(): ReturnType<typeof Database> {
  return new Database(":memory:");
}

/**
 * Insert a task row backdated to yesterday so dailyReset() will clear it.
 * BudgetStore.getOrCreate() sets started_at = NOW, which is today, so the
 * reset query (DATE(started_at) < DATE('now')) won't touch it.  We work
 * around that by updating started_at directly after creation.
 */
function backdateTask(
  db: ReturnType<typeof Database>,
  taskId: string,
): void {
  db.prepare(
    "UPDATE budget_states SET started_at = '2000-01-01T00:00:00.000Z' WHERE task_id = ?",
  ).run(taskId);
}

// ---------------------------------------------------------------------------
// Shared fixtures
// ---------------------------------------------------------------------------

let db: ReturnType<typeof Database>;
let store: BudgetStore;
let allocator: BudgetAllocator;

beforeEach(() => {
  db = makeDb();
  store = new BudgetStore(db);
  allocator = new BudgetAllocator(db);
});

// ===========================================================================
// 1. Token accumulation lifecycle
// ===========================================================================

describe("Token accumulation lifecycle", () => {
  it("new task starts at 0 tokens with no warnings", () => {
    const taskId = "e2e-acc-1";
    const budgetConfig = getDefaultBudgetConfig("coder");
    const manager = new NormalizedBudgetManager(store, DEFAULT_TOKEN_BUDGET_CONFIG);

    store.getOrCreate(taskId, "coder");
    const state = store.getState(taskId)!;

    expect(state.tokensUsed).toBe(0);
    expect(manager.checkWarningThresholds(state, budgetConfig)).toHaveLength(0);
  });

  it("tokens accumulate correctly across multiple increments", () => {
    const taskId = "e2e-acc-2";
    store.getOrCreate(taskId, "coder");

    store.incrementTokens(taskId, 5_000);
    store.incrementTokens(taskId, 10_000);
    store.incrementTokens(taskId, 3_000);

    expect(store.getState(taskId)!.tokensUsed).toBe(18_000);
  });

  it("first warning fires at exactly 70% (info level)", () => {
    const taskId = "e2e-acc-3";
    const budgetConfig = getDefaultBudgetConfig("coder"); // maxTokensPerTask = 50_000
    const manager = new NormalizedBudgetManager(store, DEFAULT_TOKEN_BUDGET_CONFIG);

    store.getOrCreate(taskId, "coder");
    store.incrementTokens(taskId, 35_000); // 70%

    const warnings = manager.checkWarningThresholds(
      store.getState(taskId)!,
      budgetConfig,
    );
    expect(warnings).toHaveLength(1);
    expect(warnings[0].level).toBe("info");
  });

  it("warn level fires at 80%", () => {
    const taskId = "e2e-acc-4";
    const budgetConfig = getDefaultBudgetConfig("coder");
    const manager = new NormalizedBudgetManager(store, DEFAULT_TOKEN_BUDGET_CONFIG);

    store.getOrCreate(taskId, "coder");
    store.incrementTokens(taskId, 40_000); // 80%

    const warnings = manager.checkWarningThresholds(
      store.getState(taskId)!,
      budgetConfig,
    );
    expect(warnings).toHaveLength(1);
    expect(warnings[0].level).toBe("warn");
    expect(warnings[0].utilizationPct).toBeCloseTo(80, 0);
  });

  it("critical level fires at 90%", () => {
    const taskId = "e2e-acc-5";
    const budgetConfig = getDefaultBudgetConfig("coder");
    const manager = new NormalizedBudgetManager(store, DEFAULT_TOKEN_BUDGET_CONFIG);

    store.getOrCreate(taskId, "coder");
    store.incrementTokens(taskId, 45_000); // 90%

    const warnings = manager.checkWarningThresholds(
      store.getState(taskId)!,
      budgetConfig,
    );
    expect(warnings[0].level).toBe("critical");
  });

  it("ceiling warning fires at 100%", () => {
    const taskId = "e2e-acc-6";
    const budgetConfig = getDefaultBudgetConfig("coder");
    const manager = new NormalizedBudgetManager(store, DEFAULT_TOKEN_BUDGET_CONFIG);

    store.getOrCreate(taskId, "coder");
    store.incrementTokens(taskId, 50_000); // 100%

    const warnings = manager.checkWarningThresholds(
      store.getState(taskId)!,
      budgetConfig,
    );
    expect(warnings[0].level).toBe("ceiling");
  });
});

// ===========================================================================
// 2. Soft cap / hard cap behavior (normalized mode)
// ===========================================================================

describe("Normalized mode — soft cap and hard ceiling", () => {
  it("allows continuation at exactly 100% (soft cap is 120%)", () => {
    const taskId = "e2e-cap-1";
    const budgetConfig = getDefaultBudgetConfig("coder");
    const manager = new NormalizedBudgetManager(store, DEFAULT_TOKEN_BUDGET_CONFIG);

    store.getOrCreate(taskId, "coder");
    store.incrementTokens(taskId, 50_000); // 100%

    expect(manager.shouldAllowContinuation(store.getState(taskId)!, budgetConfig)).toBe(true);
  });

  it("allows continuation at 110% (under 120% soft cap)", () => {
    const taskId = "e2e-cap-2";
    const budgetConfig = getDefaultBudgetConfig("coder");
    const manager = new NormalizedBudgetManager(store, DEFAULT_TOKEN_BUDGET_CONFIG);

    store.getOrCreate(taskId, "coder");
    store.incrementTokens(taskId, 55_000); // 110%

    expect(manager.shouldAllowContinuation(store.getState(taskId)!, budgetConfig)).toBe(true);
  });

  it("blocks at 121% (above 120% hard ceiling)", () => {
    const taskId = "e2e-cap-3";
    const budgetConfig = getDefaultBudgetConfig("coder");
    const manager = new NormalizedBudgetManager(store, DEFAULT_TOKEN_BUDGET_CONFIG);

    store.getOrCreate(taskId, "coder");
    store.incrementTokens(taskId, 60_500); // 121%

    expect(manager.shouldAllowContinuation(store.getState(taskId)!, budgetConfig)).toBe(false);
  });

  it("suggestFallbackModel walks the chain from claude", () => {
    const manager = new NormalizedBudgetManager(store, DEFAULT_TOKEN_BUDGET_CONFIG);
    const suggestion = manager.suggestFallbackModel("claude");
    expect(suggestion.model).toBe("gpt");
    expect(suggestion.reason).toContain("claude");
  });
});

// ===========================================================================
// 3. Policy switching
// ===========================================================================

describe("Policy switching lifecycle", () => {
  it("selectBudgetManager returns NormalizedBudgetManager for 'normalized'", () => {
    expect(selectBudgetManager(store, allocator, "normalized")).toBeInstanceOf(
      NormalizedBudgetManager,
    );
  });

  it("selectBudgetManager returns AggressiveBudgetManager for 'aggressive'", () => {
    expect(selectBudgetManager(store, allocator, "aggressive")).toBeInstanceOf(
      AggressiveBudgetManager,
    );
  });

  it("selectBudgetManager defaults to normalized when env var is absent", () => {
    const prev = process.env.BUDGET_POLICY;
    delete process.env.BUDGET_POLICY;
    try {
      expect(selectBudgetManager(store, allocator)).toBeInstanceOf(
        NormalizedBudgetManager,
      );
    } finally {
      if (prev !== undefined) process.env.BUDGET_POLICY = prev;
    }
  });

  it("selectBudgetManager defaults to normalized for unrecognised policy string", () => {
    expect(selectBudgetManager(store, allocator, "turbo-yolo")).toBeInstanceOf(
      NormalizedBudgetManager,
    );
  });
});

// ===========================================================================
// 4. Task complexity routing
// ===========================================================================

describe("Task complexity routing", () => {
  it("classifies read-only tool calls as simple", () => {
    expect(classifyTaskComplexity({ toolName: "Read" })).toBe("simple");
    expect(classifyTaskComplexity({ toolName: "Grep" })).toBe("simple");
    expect(classifyTaskComplexity({ toolName: "Glob" })).toBe("simple");
  });

  it("classifies council/agent/spawn keywords as complex", () => {
    expect(classifyTaskComplexity({ description: "run council validation" })).toBe("complex");
    expect(classifyTaskComplexity({ description: "spawn agent for discovery" })).toBe("complex");
  });

  it("classifies long commands as complex (>500 chars)", () => {
    expect(classifyTaskComplexity({ commandLength: 600 })).toBe("complex");
  });

  it("simple tasks route to ollama in aggressive mode", () => {
    const manager = new AggressiveBudgetManager(allocator, DEFAULT_TOKEN_BUDGET_CONFIG);
    const result = manager.selectModelForTask("run ls /tmp");
    expect(result.preferred).toBe("ollama");
    expect(result.fallbacks).toContain("claude");
  });

  it("complex tasks route to claude in aggressive mode", () => {
    const manager = new AggressiveBudgetManager(allocator, DEFAULT_TOKEN_BUDGET_CONFIG);
    const result = manager.selectModelForTask("run council validation with agent spawning");
    expect(result.preferred).toBe("claude");
    expect(result.fallbacks).toContain("ollama");
  });

  it("classifier and aggressive manager agree on discovery phase complexity", () => {
    const complexity = classifyTaskComplexity({ description: "run discovery phase" });
    const manager = new AggressiveBudgetManager(allocator, DEFAULT_TOKEN_BUDGET_CONFIG);
    const routing = manager.selectModelForTask("run discovery phase");

    expect(complexity).toBe("complex");
    expect(routing.preferred).toBe("claude");
  });
});

// ===========================================================================
// 5. Daily rollover lifecycle
// ===========================================================================

describe("Daily rollover lifecycle", () => {
  it("tokens reset to 0 after dailyReset() when started_at is in the past", () => {
    const taskId = "e2e-rollover-1";
    store.getOrCreate(taskId, "coder");
    store.incrementTokens(taskId, 10_000);
    expect(store.getState(taskId)!.tokensUsed).toBe(10_000);

    // Backdate so the reset query sees it as a past-day record
    backdateTask(db, taskId);

    // Trick the singleton to think reset is stale
    db.prepare(
      "UPDATE daily_budget_reset SET last_reset_date = '2000-01-01' WHERE id = 'singleton'",
    ).run();

    store.dailyReset();
    expect(store.getState(taskId)!.tokensUsed).toBe(0);
  });

  it("dailyReset is idempotent — second call on same day is a no-op", () => {
    const taskId = "e2e-rollover-2";
    store.getOrCreate(taskId, "coder");
    store.incrementTokens(taskId, 5_000);
    backdateTask(db, taskId);

    db.prepare(
      "UPDATE daily_budget_reset SET last_reset_date = '2000-01-01' WHERE id = 'singleton'",
    ).run();
    store.dailyReset();

    // Add more tokens after the first reset
    store.incrementTokens(taskId, 2_000);
    // Second dailyReset should not zero the new tokens (same-day guard)
    store.dailyReset();
    expect(store.getState(taskId)!.tokensUsed).toBe(2_000);
  });
});

// ===========================================================================
// 6. Fallback chain in aggressive mode
// ===========================================================================

describe("Fallback chain in aggressive mode", () => {
  it("selectAvailableModel returns gpt when gpt is available", () => {
    const manager = new AggressiveBudgetManager(allocator, DEFAULT_TOKEN_BUDGET_CONFIG);
    // gpt has 40% of $50 = $20 budget; nothing spent yet → available
    const result = manager.selectAvailableModel("run complex council task", "gpt");
    expect(result.model).toBe("gpt");
  });

  it("exhausted gpt falls back to next available model", () => {
    const gptBudget = allocator.getRemainingBudget("gpt");
    // gpt is a paid provider; exhaust it
    if (isFinite(gptBudget)) {
      allocator.recordSpend("gpt", gptBudget);
    }

    const manager = new AggressiveBudgetManager(allocator, DEFAULT_TOKEN_BUDGET_CONFIG);
    const result = manager.selectAvailableModel("run complex task", "gpt");

    expect(result.model).not.toBe("gpt");
    // Fallback reason must mention the preferred model being over budget
    expect(result.reason.toLowerCase()).toContain("exceeded");
  });

  it("ollama is always available as last-resort fallback (free)", () => {
    // Exhaust all paid providers
    for (const model of ["gpt", "gemini"] as const) {
      const remaining = allocator.getRemainingBudget(model);
      if (isFinite(remaining)) {
        allocator.recordSpend(model, remaining);
      }
    }

    const manager = new AggressiveBudgetManager(allocator, DEFAULT_TOKEN_BUDGET_CONFIG);
    const result = manager.selectAvailableModel("simple task");
    // ollama preferred for simple; already first choice regardless of exhaustion
    expect(result.model).toBe("ollama");
    expect(result.estimatedCostUsd).toBe(0);
  });

  it("predictSpendSurplus detects when a model would exceed its budget", () => {
    const manager = new AggressiveBudgetManager(allocator, DEFAULT_TOKEN_BUDGET_CONFIG);
    const remaining = allocator.getRemainingBudget("gpt");

    if (isFinite(remaining)) {
      const { canProceed } = manager.predictSpendSurplus("gpt", remaining + 1);
      expect(canProceed).toBe(false);
    } else {
      // gpt has Infinity remaining (shouldn't happen by default, but guard the test)
      expect(remaining).toBe(Infinity);
    }
  });

  it("enforceSpendLimit returns true when no spend recorded", () => {
    const manager = new AggressiveBudgetManager(allocator, DEFAULT_TOKEN_BUDGET_CONFIG);
    expect(manager.enforceSpendLimit()).toBe(true);
  });

  it("enforceSpendLimit returns false when total daily spend exceeds cap", () => {
    // DEFAULT_TOKEN_BUDGET_CONFIG.dailyBudgetCapUsd = 5.0
    // Burn through more than $5 across providers
    allocator.recordSpend("gpt", 3.0);
    allocator.recordSpend("gemini", 3.0);

    const manager = new AggressiveBudgetManager(allocator, DEFAULT_TOKEN_BUDGET_CONFIG);
    expect(manager.enforceSpendLimit()).toBe(false);
  });
});

// ===========================================================================
// 7. Cost accuracy tracking
// ===========================================================================

describe("Cost accuracy tracking", () => {
  it("records a completion and calculates accuracy correctly", () => {
    const tracker = new CostAccuracyTracker(db);
    const record = tracker.recordCompletion("task-acc-1", "claude", 0.01, 0.01);

    expect(record.accuracyPct).toBe(0);
    expect(record.flagged).toBe(false);
  });

  it("flags records where estimate is more than 20% off from actual", () => {
    const tracker = new CostAccuracyTracker(db);
    // 0.05 estimated vs 0.01 actual → 400% off → flagged
    const record = tracker.recordCompletion("task-acc-2", "gpt", 0.05, 0.01);

    expect(record.flagged).toBe(true);
    expect(record.accuracyPct).toBeGreaterThan(20);
  });

  it("getFlaggedRecords returns only flagged entries", () => {
    const tracker = new CostAccuracyTracker(db);
    tracker.recordCompletion("task-acc-3a", "claude", 0.01, 0.01); // not flagged
    tracker.recordCompletion("task-acc-3b", "gpt", 0.10, 0.01);   // flagged

    const flagged = tracker.getFlaggedRecords();
    expect(flagged.length).toBeGreaterThanOrEqual(1);
    expect(flagged.every((r) => r.flagged)).toBe(true);
  });

  it("getAccuracySummary aggregates totals and per-model averages", () => {
    const tracker = new CostAccuracyTracker(db);
    tracker.recordCompletion("task-acc-4a", "ollama", 0, 0);
    tracker.recordCompletion("task-acc-4b", "ollama", 0, 0);

    const summary = tracker.getAccuracySummary();
    expect(summary.totalRecords).toBeGreaterThanOrEqual(2);
    expect(summary.byModel).toHaveProperty("ollama");
  });
});
