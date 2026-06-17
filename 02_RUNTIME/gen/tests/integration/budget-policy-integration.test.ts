/**
 * L2 integration tests: hooks + budget manager interaction.
 * Verifies that PreToolUse calls NormalizedBudgetManager.checkWarningThresholds
 * and PostToolUse calls budgetStore.incrementTokens.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import Database from "better-sqlite3";
import { BudgetStore } from "../../src/budget/budget-store.js";
import { BudgetAllocator } from "../../src/budget/budget-allocator.js";
import { NormalizedBudgetManager } from "../../src/budget/normalized-budget-manager.js";
import { AggressiveBudgetManager } from "../../src/budget/aggressive-budget-manager.js";
import { selectBudgetManager } from "../../src/budget/budget-policy-selector.js";
import { BudgetPolicy, DEFAULT_TOKEN_BUDGET_CONFIG } from "../../src/budget/budget-types.js";
import { getDefaultBudgetConfig } from "../../src/budget/budget-config.js";

describe("budget-policy-integration", () => {
  let db: ReturnType<typeof Database>;
  let store: BudgetStore;
  let allocator: BudgetAllocator;

  beforeEach(() => {
    db = new Database(":memory:");
    store = new BudgetStore(db);
    allocator = new BudgetAllocator(db);
  });

  afterEach(() => {
    db.close();
  });

  it("selectBudgetManager returns NormalizedBudgetManager for 'normalized'", () => {
    const manager = selectBudgetManager(store, allocator, "normalized");
    expect(manager).toBeInstanceOf(NormalizedBudgetManager);
  });

  it("selectBudgetManager returns AggressiveBudgetManager for 'aggressive'", () => {
    const manager = selectBudgetManager(store, allocator, "aggressive");
    expect(manager).toBeInstanceOf(AggressiveBudgetManager);
  });

  it("selectBudgetManager defaults to NormalizedBudgetManager for invalid policy", () => {
    const manager = selectBudgetManager(store, allocator, "turbo-yolo");
    expect(manager).toBeInstanceOf(NormalizedBudgetManager);
  });

  it("PostToolUse token counting: incrementTokens called and state updates", () => {
    const taskId = "integration-task-1";
    store.getOrCreate(taskId, "coder");

    store.incrementTokens(taskId, 150);

    const state = store.getState(taskId)!;
    expect(state.tokensUsed).toBe(150);
  });

  it("NormalizedBudgetManager: no warnings below 70%", () => {
    const budgetConfig = getDefaultBudgetConfig("coder");
    const manager = new NormalizedBudgetManager(store, DEFAULT_TOKEN_BUDGET_CONFIG);
    const taskId = "integration-task-2";

    store.getOrCreate(taskId, "coder");
    store.incrementTokens(taskId, Math.floor(budgetConfig.maxTokensPerTask * 0.5));
    const state = store.getState(taskId)!;

    expect(manager.checkWarningThresholds(state, budgetConfig)).toHaveLength(0);
  });

  it("NormalizedBudgetManager: warn at 80%", () => {
    const budgetConfig = getDefaultBudgetConfig("coder");
    const manager = new NormalizedBudgetManager(store, DEFAULT_TOKEN_BUDGET_CONFIG);
    const taskId = "integration-task-3";

    store.getOrCreate(taskId, "coder");
    store.incrementTokens(taskId, Math.floor(budgetConfig.maxTokensPerTask * 0.82));
    const state = store.getState(taskId)!;

    const warnings = manager.checkWarningThresholds(state, budgetConfig);
    expect(warnings.length).toBeGreaterThan(0);
    expect(warnings[0].level).toBe("warn");
  });

  it("NormalizedBudgetManager: allows continuation at 100% (not at 120% soft cap yet)", () => {
    const budgetConfig = getDefaultBudgetConfig("coder");
    const manager = new NormalizedBudgetManager(store, DEFAULT_TOKEN_BUDGET_CONFIG);
    const taskId = "integration-task-4";

    store.getOrCreate(taskId, "coder");
    store.incrementTokens(taskId, budgetConfig.maxTokensPerTask);
    const state = store.getState(taskId)!;

    expect(manager.shouldAllowContinuation(state, budgetConfig)).toBe(true);
  });

  it("NormalizedBudgetManager: blocks at 121% (over soft cap)", () => {
    const budgetConfig = getDefaultBudgetConfig("coder");
    const manager = new NormalizedBudgetManager(store, DEFAULT_TOKEN_BUDGET_CONFIG);
    const taskId = "integration-task-5";

    store.getOrCreate(taskId, "coder");
    store.incrementTokens(taskId, Math.floor(budgetConfig.maxTokensPerTask * 1.21));
    const state = store.getState(taskId)!;

    expect(manager.shouldAllowContinuation(state, budgetConfig)).toBe(false);
  });

  it("policy env var: BUDGET_POLICY=aggressive selects AggressiveBudgetManager", () => {
    const prev = process.env.BUDGET_POLICY;
    process.env.BUDGET_POLICY = "aggressive";
    try {
      const manager = selectBudgetManager(store, allocator);
      expect(manager).toBeInstanceOf(AggressiveBudgetManager);
    } finally {
      if (prev === undefined) delete process.env.BUDGET_POLICY;
      else process.env.BUDGET_POLICY = prev;
    }
  });
});
