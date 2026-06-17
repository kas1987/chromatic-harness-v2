import { describe, it, expect } from "vitest";
import { estimateCost, actualCost } from "../../src/budget/model-cost-calculator.js";
import type { LlmTask } from "../../src/llm/llm-types.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTask(overrides: Partial<LlmTask> = {}): LlmTask {
  return {
    intent: "code",
    scope: "simple",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// estimateCost()
// ---------------------------------------------------------------------------

describe("estimateCost", () => {
  it("EstimateCost_Ollama_ReturnsZero: ollama always returns exactly 0", () => {
    const task = makeTask({ intent: "code", scope: "simple" });
    expect(estimateCost(task, "ollama", 1000, 500)).toBe(0);
  });

  it("EstimateCost_Ollama_ReturnsZero_LargeTokens: zero regardless of token count", () => {
    const task = makeTask();
    expect(estimateCost(task, "ollama", 100_000, 50_000)).toBe(0);
  });

  it("EstimateCost_Claude_MaxPlan_ReturnsZero: claude is $0 under Max plan (flat subscription, no per-token billing)", () => {
    const task = makeTask();
    // Claude Max plan: costPer1kInput=0, costPer1kOutput=0 — covered by flat subscription fee
    const result = estimateCost(task, "claude", 1000, 500);
    expect(result).toBe(0);
  });

  it("EstimateCost_Claude_MaxPlan_ZeroRegardlessOfTokens: zero for any token count", () => {
    const task = makeTask();
    expect(estimateCost(task, "claude", 1000, 1000)).toBe(0);
    expect(estimateCost(task, "claude", 100_000, 50_000)).toBe(0);
  });

  it("EstimateCost_Claude_CheaperThanGpt: claude (Max plan, $0) is cheaper than gpt (metered)", () => {
    const task = makeTask();
    const claudeCost = estimateCost(task, "claude", 1000, 500);
    const gptCost = estimateCost(task, "gpt", 1000, 500);
    // Claude = $0 (Max plan), GPT = metered API call > $0
    expect(claudeCost).toBeLessThan(gptCost);
  });

  it("EstimateCost_Gpt_CorrectFormula: (2000/1000)*0.00015 + (500/1000)*0.0006", () => {
    const task = makeTask();
    // gpt: costPer1kInput=0.00015, costPer1kOutput=0.0006
    // (2000/1000)*0.00015 + (500/1000)*0.0006 = 0.0003 + 0.0003 = 0.0006
    const result = estimateCost(task, "gpt", 2000, 500);
    expect(result).toBeCloseTo(0.0006, 7);
  });

  it("CostComparison_Gemini_CheaperThanGpt: gemini < gpt for large input tokens", () => {
    const task = makeTask();
    // gemini: costPer1kInput=0.0001, gpt: costPer1kInput=0.00015
    const geminiCost = estimateCost(task, "gemini", 100_000, 10_000);
    const gptCost = estimateCost(task, "gpt", 100_000, 10_000);
    expect(geminiCost).toBeLessThan(gptCost);
  });

  it("zero tokens returns zero cost for any provider", () => {
    const task = makeTask();
    expect(estimateCost(task, "claude", 0, 0)).toBe(0);
    expect(estimateCost(task, "gpt", 0, 0)).toBe(0);
    expect(estimateCost(task, "gemini", 0, 0)).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// actualCost()
// ---------------------------------------------------------------------------

describe("actualCost", () => {
  it("ActualCost_Claude_MaxPlan_Zero: actualCost for claude is $0 under Max plan", () => {
    const task = makeTask();
    const estimated = estimateCost(task, "claude", 1000, 500);
    const actual = actualCost(1000, 500, "claude");
    expect(actual).toBe(0);
    expect(actual).toBe(estimated);
  });

  it("ActualCost_Ollama_ReturnsZero: ollama actual cost is exactly 0", () => {
    expect(actualCost(5000, 2000, "ollama")).toBe(0);
  });

  it("ActualCost_Gpt_CorrectFormula: (2000/1000)*0.00015 + (500/1000)*0.0006 = 0.0006", () => {
    const result = actualCost(2000, 500, "gpt");
    expect(result).toBeCloseTo(0.0006, 7);
  });

  it("ActualCost_Claude_MaxPlan_AlwaysZero: zero at all scales under Max plan", () => {
    const inputs = [
      [500, 250],
      [5000, 1000],
      [50_000, 10_000],
    ] as const;
    for (const [input, output] of inputs) {
      const task = makeTask();
      expect(actualCost(input, output, "claude")).toBe(0);
      expect(estimateCost(task, "claude", input, output)).toBe(0);
    }
  });

  it("ActualCost_Gemini_MatchesEstimate", () => {
    const task = makeTask();
    const estimated = estimateCost(task, "gemini", 10_000, 5_000);
    const actual = actualCost(10_000, 5_000, "gemini");
    expect(actual).toBeCloseTo(estimated, 9);
  });
});
