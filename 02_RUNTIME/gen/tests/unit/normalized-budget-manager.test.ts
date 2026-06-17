import { describe, it, expect, beforeEach, vi } from "vitest";
import { NormalizedBudgetManager } from "../../src/budget/normalized-budget-manager";
import type { AgentBudgetConfig, TaskBudgetState } from "../../src/budget/budget-types";
import { DEFAULT_TOKEN_BUDGET_CONFIG } from "../../src/budget/budget-types";

// Minimal BudgetStore mock — NormalizedBudgetManager holds a reference but
// none of the tested methods call through to the store.
const mockStore = {} as never;

const budgetConfig: AgentBudgetConfig = {
  agentRole: "test",
  maxTokensPerTask: 50_000,
  maxTokensPerDay: 500_000,
  maxExternalCallsPerTask: 100,
  maxWallTimeSecondsPerTask: 3600,
  maxHandoffs: 5,
  thresholds: { warnPct: 70, hardStopPct: 95 },
};

function makeState(tokensUsed: number): TaskBudgetState {
  return {
    taskId: "task-1",
    agentRole: "test",
    tokensUsed,
    externalCalls: 3,
    handoffs: 0,
    wallTimeSeconds: 120,
    startedAt: new Date().toISOString(),
    warnings: [],
    stopped: false,
  };
}

describe("NormalizedBudgetManager", () => {
  let manager: NormalizedBudgetManager;

  beforeEach(() => {
    manager = new NormalizedBudgetManager(mockStore, DEFAULT_TOKEN_BUDGET_CONFIG);
  });

  // --- checkWarningThresholds ---

  it("returns info warning at 70% utilization", () => {
    const state = makeState(35_000); // 70% of 50_000
    const warnings = manager.checkWarningThresholds(state, budgetConfig);
    expect(warnings).toHaveLength(1);
    expect(warnings[0].level).toBe("info");
    expect(warnings[0].message).toContain("Moderate");
    expect(warnings[0].utilizationPct).toBe(70);
  });

  it("returns warn warning at 80% utilization", () => {
    const state = makeState(40_000); // 80% of 50_000
    const warnings = manager.checkWarningThresholds(state, budgetConfig);
    expect(warnings).toHaveLength(1);
    expect(warnings[0].level).toBe("warn");
    expect(warnings[0].message).toContain("High");
    expect(warnings[0].utilizationPct).toBe(80);
  });

  it("returns ceiling warning at 100% utilization", () => {
    const state = makeState(50_000); // 100% of 50_000
    const warnings = manager.checkWarningThresholds(state, budgetConfig);
    expect(warnings).toHaveLength(1);
    expect(warnings[0].level).toBe("ceiling");
    expect(warnings[0].message).toContain("ceiling");
    expect(warnings[0].utilizationPct).toBe(100);
  });

  it("returns no warnings below 70% utilization", () => {
    const state = makeState(20_000); // 40% of 50_000
    const warnings = manager.checkWarningThresholds(state, budgetConfig);
    expect(warnings).toHaveLength(0);
  });

  // --- shouldAllowContinuation ---

  it("allows continuation at 80% (under soft cap)", () => {
    const state = makeState(40_000); // 80%
    expect(manager.shouldAllowContinuation(state, budgetConfig)).toBe(true);
  });

  it("allows continuation at exactly 100% (soft cap is 120%)", () => {
    const state = makeState(50_000); // 100%
    expect(manager.shouldAllowContinuation(state, budgetConfig)).toBe(true);
  });

  it("blocks continuation at 121% (just over 120% soft cap)", () => {
    const state = makeState(60_500); // 121% of 50_000
    expect(manager.shouldAllowContinuation(state, budgetConfig)).toBe(false);
  });

  // --- suggestFallbackModel ---

  it("suggests gpt as fallback for claude", () => {
    const suggestion = manager.suggestFallbackModel("claude");
    expect(suggestion.model).toBe("gpt");
  });

  it("suggests gemini as fallback for gpt", () => {
    const suggestion = manager.suggestFallbackModel("gpt");
    expect(suggestion.model).toBe("gemini");
  });

  // --- summarizeSession ---

  it("summarizes session with 1 warning at 80% usage", () => {
    const state = makeState(40_000); // 80%
    const summary = manager.summarizeSession("sess-1", state, budgetConfig);
    expect(summary.tokensUsed).toBe(40_000);
    expect(summary.callsUsed).toBe(3);
    expect(summary.timeUsed).toBe(120);
    expect(summary.budgetPct).toBe(80);
    expect(summary.warnings).toHaveLength(1);
    expect(summary.warnings[0].level).toBe("warn");
  });
});
