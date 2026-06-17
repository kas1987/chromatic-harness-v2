import { describe, it, expect } from "vitest";
import { BudgetPolicy, DEFAULT_TOKEN_BUDGET_CONFIG } from "../../src/budget/budget-types.js";
import { parseBudgetPolicy, getActiveBudgetPolicy } from "../../src/budget/budget-policy-selector.js";

describe("BudgetPolicy enum", () => {
  it("NORMALIZED has value 'normalized'", () => {
    expect(BudgetPolicy.NORMALIZED).toBe("normalized");
  });

  it("AGGRESSIVE has value 'aggressive'", () => {
    expect(BudgetPolicy.AGGRESSIVE).toBe("aggressive");
  });
});

describe("DEFAULT_TOKEN_BUDGET_CONFIG", () => {
  it("has expected maxTokensPerTask", () => {
    expect(DEFAULT_TOKEN_BUDGET_CONFIG.maxTokensPerTask).toBe(50_000);
  });

  it("normalizedSoftCapPercent is 120", () => {
    expect(DEFAULT_TOKEN_BUDGET_CONFIG.normalizedSoftCapPercent).toBe(120);
  });
});

describe("parseBudgetPolicy", () => {
  it("returns NORMALIZED for 'normalized'", () => {
    expect(parseBudgetPolicy("normalized")).toBe(BudgetPolicy.NORMALIZED);
  });

  it("returns AGGRESSIVE for 'aggressive'", () => {
    expect(parseBudgetPolicy("aggressive")).toBe(BudgetPolicy.AGGRESSIVE);
  });

  it("returns NORMALIZED (default) for invalid value", () => {
    expect(parseBudgetPolicy("invalid-value")).toBe(BudgetPolicy.NORMALIZED);
  });

  it("returns NORMALIZED for undefined (uses env var or default)", () => {
    delete process.env.BUDGET_POLICY;
    expect(parseBudgetPolicy(undefined)).toBe(BudgetPolicy.NORMALIZED);
  });

  it("reads from BUDGET_POLICY env var when no argument passed", () => {
    process.env.BUDGET_POLICY = "aggressive";
    expect(parseBudgetPolicy()).toBe(BudgetPolicy.AGGRESSIVE);
    delete process.env.BUDGET_POLICY;
  });
});
