import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { parseBudgetPolicy } from "../../src/budget/budget-policy-selector.js";
import { BudgetPolicy } from "../../src/budget/budget-types.js";

describe("budget-policy-runtime", () => {
  let originalPolicy: string | undefined;

  beforeEach(() => {
    originalPolicy = process.env.BUDGET_POLICY;
  });

  afterEach(() => {
    if (originalPolicy === undefined) {
      delete process.env.BUDGET_POLICY;
    } else {
      process.env.BUDGET_POLICY = originalPolicy;
    }
  });

  it("defaults to normalized when BUDGET_POLICY env var not set", () => {
    delete process.env.BUDGET_POLICY;
    expect(parseBudgetPolicy()).toBe(BudgetPolicy.NORMALIZED);
  });

  it("reads BUDGET_POLICY=aggressive from env var", () => {
    process.env.BUDGET_POLICY = "aggressive";
    expect(parseBudgetPolicy()).toBe(BudgetPolicy.AGGRESSIVE);
  });

  it("returns normalized for invalid BUDGET_POLICY value", () => {
    process.env.BUDGET_POLICY = "invalid";
    expect(parseBudgetPolicy()).toBe(BudgetPolicy.NORMALIZED);
  });

  it("is case-insensitive (AGGRESSIVE → aggressive)", () => {
    expect(parseBudgetPolicy("AGGRESSIVE")).toBe(BudgetPolicy.AGGRESSIVE);
  });
});
