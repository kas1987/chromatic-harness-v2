import { describe, it, expect, beforeEach } from "vitest";
import Database from "better-sqlite3";
import { BudgetStore } from "../../src/budget/budget-store";

function openMemoryDb(): Database.Database {
  return new Database(":memory:");
}

describe("Token counting in PostToolUse hook", () => {
  let db: Database.Database;
  let store: BudgetStore;

  beforeEach(() => {
    db = openMemoryDb();
    store = new BudgetStore(db);
  });

  it("records tokens when result.tokens is present", () => {
    const taskId = "test-task";
    store.getOrCreate(taskId, "system");

    // Simulate the hook's token extraction logic (result.tokens path)
    const result: any = { tokens: 150 };
    const tokenCount =
      typeof result?.tokens === "number"
        ? result.tokens
        : typeof result?.token_count === "number"
          ? result.token_count
          : null;

    expect(tokenCount).toBe(150);
    store.incrementTokens(taskId, tokenCount!);

    const state = store.getState(taskId);
    expect(state?.tokensUsed).toBe(150);
  });

  it("handles missing token count gracefully (result has no tokens field)", () => {
    const taskId = "test-task-no-tokens";
    store.getOrCreate(taskId, "system");

    // Simulate the hook's token extraction logic — no tokens field
    const result: any = { output: "some output" };
    const tokenCount =
      typeof result?.tokens === "number"
        ? result.tokens
        : typeof result?.token_count === "number"
          ? result.token_count
          : null;

    // tokenCount is null — incrementTokens should NOT be called
    expect(tokenCount).toBeNull();

    // Do NOT call incrementTokens — verify state is unchanged
    const state = store.getState(taskId);
    expect(state?.tokensUsed).toBe(0);
  });

  it("accumulates tokens across multiple PostToolUse calls", () => {
    const taskId = "test-task-accumulate";
    store.getOrCreate(taskId, "system");

    // First call: tokens = 100
    const result1: any = { tokens: 100 };
    const tokenCount1 =
      typeof result1?.tokens === "number"
        ? result1.tokens
        : typeof result1?.token_count === "number"
          ? result1.token_count
          : null;

    if (tokenCount1 !== null) {
      store.incrementTokens(taskId, tokenCount1);
    }

    // Second call: token_count = 50 (alternate field name)
    const result2: any = { token_count: 50 };
    const tokenCount2 =
      typeof result2?.tokens === "number"
        ? result2.tokens
        : typeof result2?.token_count === "number"
          ? result2.token_count
          : null;

    if (tokenCount2 !== null) {
      store.incrementTokens(taskId, tokenCount2);
    }

    const state = store.getState(taskId);
    expect(state?.tokensUsed).toBe(150);
  });
});
