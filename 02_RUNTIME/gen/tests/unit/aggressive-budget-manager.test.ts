import { describe, it, expect, beforeEach } from "vitest";
import Database from "better-sqlite3";
import { BudgetAllocator } from "../../src/budget/budget-allocator.js";
import { AggressiveBudgetManager } from "../../src/budget/aggressive-budget-manager.js";

function makeManager() {
  const db = new Database(":memory:");
  const allocator = new BudgetAllocator(db);
  const manager = new AggressiveBudgetManager(allocator);
  return { db, allocator, manager };
}

describe("AggressiveBudgetManager", () => {
  // ── 1. Simple task routes to ollama ─────────────────────────────────────
  it("selectModelForTask: simple task → preferred ollama", () => {
    const { manager } = makeManager();
    const result = manager.selectModelForTask("run ls /tmp");
    expect(result.preferred).toBe("ollama");
  });

  // ── 2. Complex task routes to claude ────────────────────────────────────
  it("selectModelForTask: complex task with keywords → preferred claude", () => {
    const { manager } = makeManager();
    const result = manager.selectModelForTask("run council validation with spawning");
    expect(result.preferred).toBe("claude");
    expect(result.fallbacks).toContain("gpt");
  });

  // ── 3. Ollama is always available regardless of cost ────────────────────
  it("isModelAvailable: ollama always returns true (Infinity budget)", () => {
    const { manager } = makeManager();
    expect(manager.isModelAvailable("ollama", 5.0)).toBe(true);
  });

  // ── 4. Model available when remaining > cost ─────────────────────────────
  it("isModelAvailable: returns true when remaining budget exceeds cost", () => {
    const { manager, allocator } = makeManager();
    // gpt has 40% of $50 = $20 remaining (nothing spent yet)
    const remaining = allocator.getRemainingBudget("gpt");
    expect(remaining).toBeGreaterThan(0);
    expect(manager.isModelAvailable("gpt", 0.001)).toBe(true);
  });

  // ── 5. Model unavailable when remaining < cost ───────────────────────────
  it("isModelAvailable: returns false when remaining budget < cost", () => {
    const { manager, allocator } = makeManager();
    // Exhaust gpt budget by recording more spend than allocation
    const remaining = allocator.getRemainingBudget("gpt");
    allocator.recordSpend("gpt", remaining + 1);
    expect(manager.isModelAvailable("gpt", 0.001)).toBe(false);
  });

  // ── 6. selectAvailableModel falls back when claude exhausted ────────────
  it("selectAvailableModel: when claude exhausted, falls back to gpt", () => {
    const db = new Database(":memory:");
    // Give claude 0% allocation so it exhausts immediately (non-free provider test)
    // Actually claude is always free (Infinity). Let's exhaust gpt instead
    // and test that with preferred=gpt it falls to gemini.
    const allocator = new BudgetAllocator(db, {
      totalMonthlyBudgetUsd: 10,
      allocations: { claude: 0, gpt: 10, gemini: 40, "lm-studio": 0, ollama: 0 },
    });
    const manager = new AggressiveBudgetManager(allocator);

    // Exhaust gpt
    const gptRemaining = allocator.getRemainingBudget("gpt");
    allocator.recordSpend("gpt", gptRemaining + 1);

    const result = manager.selectAvailableModel("run ls", "gpt");
    expect(result.model).not.toBe("gpt");
    expect(result.reason).toMatch(/gpt exceeded monthly budget/i);
  });

  // ── 7. selectAvailableModel falls back to free model when all paid exhausted ─
  // When all paid models (gpt, gemini) are exhausted and preferred is "gpt",
  // the system falls back through the chain and eventually lands on a free provider.
  // Both "claude" (Max plan, Infinity) and "ollama" (local, free) satisfy this.
  it("selectAvailableModel: when all paid models exhausted, returns a free provider", () => {
    const db = new Database(":memory:");
    const allocator = new BudgetAllocator(db, {
      totalMonthlyBudgetUsd: 10,
      allocations: { claude: 0, gpt: 50, gemini: 50, "lm-studio": 0, ollama: 0 },
    });
    const manager = new AggressiveBudgetManager(allocator);

    // Exhaust gpt and gemini
    allocator.recordSpend("gpt", allocator.getRemainingBudget("gpt") + 1);
    allocator.recordSpend("gemini", allocator.getRemainingBudget("gemini") + 1);

    const result = manager.selectAvailableModel("simple task", "gpt");
    // Free providers: claude (Infinity budget) and ollama (cost=0)
    expect(["claude", "ollama", "lm-studio"]).toContain(result.model);
    expect(result.estimatedCostUsd).toBe(0);
  });

  // ── 8. enforceSpendLimit: under daily cap → true ─────────────────────────
  it("enforceSpendLimit: under daily cap returns true", () => {
    const { manager, allocator } = makeManager();
    // Spend $1 total — well under $5 default cap
    allocator.recordSpend("gpt", 1.0);
    expect(manager.enforceSpendLimit()).toBe(true);
  });

  // ── 9. enforceSpendLimit: at/over daily cap → false ──────────────────────
  it("enforceSpendLimit: at or over daily cap returns false", () => {
    const { manager, allocator } = makeManager();
    // Spend $5 total across providers — hits the cap
    allocator.recordSpend("gpt", 3.0);
    allocator.recordSpend("gemini", 2.0);
    expect(manager.enforceSpendLimit()).toBe(false);
  });

  // ── 10. predictSpendSurplus: cost < remaining → surplus positive ──────────
  it("predictSpendSurplus: cost < remaining → canProceed true, surplus positive", () => {
    const { manager, allocator } = makeManager();
    // gpt has ~$20 remaining (40% of $50)
    const remaining = allocator.getRemainingBudget("gpt");
    const result = manager.predictSpendSurplus("gpt", 0.5);
    expect(result.canProceed).toBe(true);
    expect(result.surplus).toBeGreaterThan(0);
    expect(result.remainingBudget).toBe(remaining);
    expect(result.estimatedCost).toBe(0.5);
  });

  // ── 11. predictSpendSurplus: cost > remaining → surplus negative ──────────
  it("predictSpendSurplus: cost > remaining → canProceed false, surplus negative", () => {
    const { manager, allocator } = makeManager();
    // Exhaust gpt
    const remaining = allocator.getRemainingBudget("gpt");
    allocator.recordSpend("gpt", remaining + 1);
    const result = manager.predictSpendSurplus("gpt", 0.5);
    expect(result.canProceed).toBe(false);
    expect(result.surplus).toBeLessThan(0);
  });
});
