import { describe, it, expect } from "vitest";
import { evaluateBudget } from "../../src/budget/budget-evaluator";
import { AgentBudgetConfig, TaskBudgetState } from "../../src/budget/budget-types";

function makeConfig(overrides: Partial<AgentBudgetConfig> = {}): AgentBudgetConfig {
  return {
    agentRole: "coder",
    maxTokensPerTask: 50000,
    maxTokensPerDay: 500000,
    maxExternalCallsPerTask: 20,
    maxWallTimeSecondsPerTask: 300,
    maxHandoffs: 5,
    thresholds: { warnPct: 0.8, hardStopPct: 1.0 },
    ...overrides,
  };
}

function makeState(overrides: Partial<TaskBudgetState> = {}): TaskBudgetState {
  return {
    taskId: "task-1",
    agentRole: "coder",
    tokensUsed: 0,
    externalCalls: 0,
    handoffs: 0,
    wallTimeSeconds: 0,
    startedAt: new Date().toISOString(),
    warnings: [],
    stopped: false,
    ...overrides,
  };
}

describe("evaluateBudget", () => {
  it("returns allow when all dimensions are under warn threshold", () => {
    const cfg = makeConfig();
    const state = makeState({ tokensUsed: 10000, externalCalls: 5, wallTimeSeconds: 50 });
    const result = evaluateBudget(cfg, state);

    expect(result.action).toBe("allow");
    expect(result.stopReason).toBeUndefined();
    expect(result.message).toBeUndefined();
  });

  it("returns warn when a dimension hits the warn threshold exactly", () => {
    const cfg = makeConfig();
    // 80% of 50000 = 40000 tokens
    const state = makeState({ tokensUsed: 40000 });
    const result = evaluateBudget(cfg, state);

    expect(result.action).toBe("warn");
    expect(result.message).toBeDefined();
    expect(result.message).toMatch(/80\.0%/);
    expect(result.message).toMatch(/compress reasoning/);
  });

  it("returns warn when a dimension is between warn and stop thresholds", () => {
    const cfg = makeConfig();
    const state = makeState({ tokensUsed: 45000 }); // 90%
    const result = evaluateBudget(cfg, state);

    expect(result.action).toBe("warn");
    expect(result.message).toMatch(/90\.0%/);
  });

  it("returns stop when a dimension reaches the stop threshold", () => {
    const cfg = makeConfig();
    const state = makeState({ tokensUsed: 50000 }); // 100%
    const result = evaluateBudget(cfg, state);

    expect(result.action).toBe("stop");
    expect(result.stopReason).toBeDefined();
    expect(result.stopReason).toMatch(/100\.0%/);
    expect(result.stopReason).toMatch(/Budget limit reached/);
  });

  it("returns stop when tokens exceed limit", () => {
    const cfg = makeConfig();
    const state = makeState({ tokensUsed: 60000 }); // 120%
    const result = evaluateBudget(cfg, state);

    expect(result.action).toBe("stop");
    expect(result.utilization.tokens).toBeCloseTo(1.2);
  });

  // Per-dimension: tokens independently triggers warn
  it("tokens dimension independently triggers warn", () => {
    const cfg = makeConfig();
    const state = makeState({ tokensUsed: 40001, externalCalls: 0, wallTimeSeconds: 0 });
    const result = evaluateBudget(cfg, state);

    expect(result.action).toBe("warn");
    expect(result.message).toMatch(/tokens/);
  });

  // Per-dimension: calls independently trigger warn
  it("external calls dimension independently triggers warn", () => {
    const cfg = makeConfig();
    // 80% of 20 calls = 16
    const state = makeState({ tokensUsed: 0, externalCalls: 16, wallTimeSeconds: 0 });
    const result = evaluateBudget(cfg, state);

    expect(result.action).toBe("warn");
    expect(result.message).toMatch(/calls/);
  });

  // Per-dimension: time independently triggers warn
  it("wall time dimension independently triggers warn", () => {
    const cfg = makeConfig();
    // 80% of 300s = 240s
    const state = makeState({ tokensUsed: 0, externalCalls: 0, wallTimeSeconds: 240 });
    const result = evaluateBudget(cfg, state);

    expect(result.action).toBe("warn");
    expect(result.message).toMatch(/wall time/);
  });

  // Per-dimension: calls independently trigger stop
  it("external calls dimension independently triggers stop", () => {
    const cfg = makeConfig();
    const state = makeState({ tokensUsed: 0, externalCalls: 20, wallTimeSeconds: 0 });
    const result = evaluateBudget(cfg, state);

    expect(result.action).toBe("stop");
    expect(result.stopReason).toMatch(/calls/);
  });

  // Per-dimension: time independently triggers stop
  it("wall time dimension independently triggers stop", () => {
    const cfg = makeConfig();
    const state = makeState({ tokensUsed: 0, externalCalls: 0, wallTimeSeconds: 300 });
    const result = evaluateBudget(cfg, state);

    expect(result.action).toBe("stop");
    expect(result.stopReason).toMatch(/wall time/);
  });

  it("exposes utilization ratios in all cases", () => {
    const cfg = makeConfig();
    const state = makeState({ tokensUsed: 25000, externalCalls: 10, wallTimeSeconds: 150 });
    const result = evaluateBudget(cfg, state);

    expect(result.utilization.tokens).toBeCloseTo(0.5);
    expect(result.utilization.calls).toBeCloseTo(0.5);
    expect(result.utilization.time).toBeCloseTo(0.5);
  });

  it("uses the most-utilized dimension label in stop reason", () => {
    const cfg = makeConfig();
    // Time is highest at 100%, tokens at 10%
    const state = makeState({ tokensUsed: 5000, externalCalls: 0, wallTimeSeconds: 300 });
    const result = evaluateBudget(cfg, state);

    expect(result.action).toBe("stop");
    expect(result.stopReason).toMatch(/wall time/);
  });

  it("intern hardStopPct of 0.9 stops below full utilization", () => {
    const cfg = makeConfig({
      agentRole: "intern",
      maxTokensPerTask: 10000,
      thresholds: { warnPct: 0.7, hardStopPct: 0.9 },
    });
    const state = makeState({ tokensUsed: 9000 }); // 90%
    const result = evaluateBudget(cfg, state);

    expect(result.action).toBe("stop");
  });

  it("intern warnPct of 0.7 warns earlier than coder", () => {
    const cfg = makeConfig({
      agentRole: "intern",
      maxTokensPerTask: 10000,
      thresholds: { warnPct: 0.7, hardStopPct: 0.9 },
    });
    const state = makeState({ tokensUsed: 7000 }); // 70%
    const result = evaluateBudget(cfg, state);

    expect(result.action).toBe("warn");
  });
});
