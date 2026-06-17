import { describe, it, expect, beforeEach } from "vitest";
import Database from "better-sqlite3";
import { BudgetAllocator } from "../../src/budget/budget-allocator.js";
import type { LlmProvider } from "../../src/llm/llm-types.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function openMemoryDb(): Database.Database {
  return new Database(":memory:");
}

interface AllocatorConfig {
  totalMonthlyBudgetUsd: number;
  allocations: Record<LlmProvider, { pct: number }>;
}

function makeConfig(overrides: Partial<AllocatorConfig> = {}): AllocatorConfig {
  return {
    totalMonthlyBudgetUsd: 100,
    allocations: {
      claude:      { pct: 0  }, // Max plan — $0 cost, Infinity budget
      gpt:         { pct: 50 },
      gemini:      { pct: 30 },
      "lm-studio": { pct: 0  }, // local — $0 cost, Infinity budget
      ollama:      { pct: 0  }, // local — $0 cost, Infinity budget
      minimax:     { pct: 0  },
      gemma:       { pct: 0  },
    },
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// BudgetAllocator.getFallbackModel() — fallback chain (I-3)
// ---------------------------------------------------------------------------

describe("BudgetAllocator.getFallbackModel", () => {
  let allocator: BudgetAllocator;

  beforeEach(() => {
    const db = openMemoryDb();
    allocator = new BudgetAllocator(db, makeConfig());
  });

  it("GetFallbackModel_Claude_ReturnsGpt: claude → gpt", () => {
    expect(allocator.getFallbackModel("claude")).toBe("gpt");
  });

  it("GetFallbackModel_Gpt_ReturnsGemini: gpt → gemini", () => {
    expect(allocator.getFallbackModel("gpt")).toBe("gemini");
  });

  it("GetFallbackModel_Gemini_ReturnsLmStudio: gemini → lm-studio", () => {
    expect(allocator.getFallbackModel("gemini")).toBe("lm-studio");
  });

  it("GetFallbackModel_LmStudio_ReturnsOllama: lm-studio → ollama", () => {
    expect(allocator.getFallbackModel("lm-studio")).toBe("ollama");
  });

  it("GetFallbackModel_Gemma_ReturnsGemma: gemma is terminal in chain", () => {
    expect(allocator.getFallbackModel("gemma")).toBe("gemma");
  });

  it("GetFallbackModel_Ollama_ReturnsGemma: next after ollama is gemma", () => {
    expect(allocator.getFallbackModel("ollama")).toBe("gemma");
  });

  it("chain traversal: claude → gpt → gemini → lm-studio → ollama → gemma (stops at end)", () => {
    const chain: LlmProvider[] = [];
    let current: LlmProvider = "claude";
    for (let i = 0; i < 8; i++) {
      const next = allocator.getFallbackModel(current);
      chain.push(next);
      if (next === current) break;
      current = next;
    }
    expect(chain[0]).toBe("gpt");
    expect(chain[1]).toBe("gemini");
    expect(chain[2]).toBe("lm-studio");
    expect(chain[3]).toBe("ollama");
    expect(chain[4]).toBe("gemma");
  });
});

// ---------------------------------------------------------------------------
// BudgetAllocator.isModelBudgetExhausted()
// ---------------------------------------------------------------------------

describe("BudgetAllocator.isModelBudgetExhausted", () => {
  it("IsModelBudgetExhausted_WhenSpentExceedsAllocation: returns true for metered provider (gpt) when spent > allocated", async () => {
    const db = openMemoryDb();
    const config = makeConfig({
      totalMonthlyBudgetUsd: 100,
      allocations: {
        claude:      { pct: 0  },
        gpt:         { pct: 10 }, // $10 allocated for gpt
        gemini:      { pct: 15 },
        "lm-studio": { pct: 0  },
        ollama:      { pct: 0  },
        minimax:     { pct: 0  },
        gemma:       { pct: 0  },
      },
    });
    const allocator = new BudgetAllocator(db, config);

    // Spend more than the $10 allocation for gpt
    await allocator.recordSpend("gpt", 11.0);

    expect(allocator.isModelBudgetExhausted("gpt")).toBe(true);
  });

  it("returns false for metered provider when spend is within allocation", async () => {
    const db = openMemoryDb();
    const config = makeConfig({
      totalMonthlyBudgetUsd: 100,
      allocations: {
        claude:      { pct: 0  },
        gpt:         { pct: 50 }, // $50 allocated for gpt
        gemini:      { pct: 15 },
        "lm-studio": { pct: 0  },
        ollama:      { pct: 0  },
        minimax:     { pct: 0  },
        gemma:       { pct: 0  },
      },
    });
    const allocator = new BudgetAllocator(db, config);

    await allocator.recordSpend("gpt", 10.0);

    expect(allocator.isModelBudgetExhausted("gpt")).toBe(false);
  });

  it("IsModelBudgetExhausted_Claude_AlwaysFalse: claude (Max plan) is never exhausted", async () => {
    const db = openMemoryDb();
    const allocator = new BudgetAllocator(db, makeConfig());

    // Even recording high spend, claude (Max plan) never exhausts
    await allocator.recordSpend("claude", 9999.0);

    expect(allocator.isModelBudgetExhausted("claude")).toBe(false);
  });

  it("IsModelBudgetExhausted_LmStudio_AlwaysFalse: lm-studio (local) is never exhausted", async () => {
    const db = openMemoryDb();
    const allocator = new BudgetAllocator(db, makeConfig());

    await allocator.recordSpend("lm-studio", 9999.0);

    expect(allocator.isModelBudgetExhausted("lm-studio")).toBe(false);
  });

  it("isModelBudgetExhausted_Ollama_AlwaysFalse: ollama is never exhausted (free)", async () => {
    const db = openMemoryDb();
    const allocator = new BudgetAllocator(db, makeConfig());

    // Even with a ridiculous spend, ollama returns false
    await allocator.recordSpend("ollama", 9999.0);

    expect(allocator.isModelBudgetExhausted("ollama")).toBe(false);
  });

  it("fresh allocator with zero spend is never exhausted", () => {
    const db = openMemoryDb();
    const allocator = new BudgetAllocator(db, makeConfig());

    expect(allocator.isModelBudgetExhausted("claude")).toBe(false);
    expect(allocator.isModelBudgetExhausted("gpt")).toBe(false);
    expect(allocator.isModelBudgetExhausted("gemini")).toBe(false);
    expect(allocator.isModelBudgetExhausted("ollama")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// BudgetAllocator.recordSpend() — DB persistence
// ---------------------------------------------------------------------------

describe("BudgetAllocator.recordSpend", () => {
  it("recordSpend accumulates across multiple calls for same model", async () => {
    const db = openMemoryDb();
    const allocator = new BudgetAllocator(db, makeConfig());

    await allocator.recordSpend("gpt", 0.005);
    await allocator.recordSpend("gpt", 0.005);

    // After two 0.005 calls, total = 0.010
    // Budget for gpt: 50% of $100 = $50. Remaining should be $50 - $0.010
    const remaining = allocator.getRemainingBudget("gpt");
    expect(remaining).toBeCloseTo(50 - 0.01, 4);
  });

  it("recordSpend does not affect other model budgets", async () => {
    const db = openMemoryDb();
    const allocator = new BudgetAllocator(db, makeConfig());

    await allocator.recordSpend("gemini", 5.0);

    // gpt remaining should be unchanged (50% of $100 = $50)
    const gptRemaining = allocator.getRemainingBudget("gpt");
    expect(gptRemaining).toBeCloseTo(50, 4);
  });

  it("recordSpend persists to DB (new allocator instance reads same state)", async () => {
    const db = openMemoryDb();
    const allocator1 = new BudgetAllocator(db, makeConfig());

    await allocator1.recordSpend("gpt", 0.005);
    await allocator1.recordSpend("gpt", 0.005);

    // A second allocator on the same DB should see the accumulated spend
    // gpt: 50% of $100 = $50. Remaining should be $50 - $0.010
    const allocator2 = new BudgetAllocator(db, makeConfig());
    const remaining = allocator2.getRemainingBudget("gpt");
    expect(remaining).toBeCloseTo(50 - 0.01, 4);
  });
});

// ---------------------------------------------------------------------------
// BudgetAllocator.getRemainingBudget()
// ---------------------------------------------------------------------------

describe("BudgetAllocator.getRemainingBudget", () => {
  it("returns full allocation when nothing spent", () => {
    const db = openMemoryDb();
    const allocator = new BudgetAllocator(db, makeConfig());

    // claude: Max plan — always Infinity (no per-token cost)
    expect(allocator.getRemainingBudget("claude")).toBe(Infinity);
    // gpt: 50% of $100 = $50
    expect(allocator.getRemainingBudget("gpt")).toBeCloseTo(50, 4);
    // gemini: 30% of $100 = $30
    expect(allocator.getRemainingBudget("gemini")).toBeCloseTo(30, 4);
  });

  it("ollama remaining budget is treated as always available (no ceiling)", () => {
    const db = openMemoryDb();
    const allocator = new BudgetAllocator(db, makeConfig());
    // ollama has 0% pct but should never be considered exhausted
    // getRemainingBudget for ollama returns a non-negative value
    const remaining = allocator.getRemainingBudget("ollama");
    expect(remaining).toBeGreaterThanOrEqual(0);
  });
});
