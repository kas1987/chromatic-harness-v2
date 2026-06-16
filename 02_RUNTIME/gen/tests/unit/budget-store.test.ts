import { describe, it, expect, beforeEach } from "vitest";
import Database from "better-sqlite3";
import { BudgetStore } from "../../src/budget/budget-store";

function openMemoryDb(): Database.Database {
  return new Database(":memory:");
}

describe("BudgetStore", () => {
  let db: Database.Database;
  let store: BudgetStore;

  beforeEach(() => {
    db = openMemoryDb();
    store = new BudgetStore(db);
  });

  it("getOrCreate creates a new record when task does not exist", () => {
    const state = store.getOrCreate("task-abc", "coder");

    expect(state.taskId).toBe("task-abc");
    expect(state.agentRole).toBe("coder");
    expect(state.tokensUsed).toBe(0);
    expect(state.externalCalls).toBe(0);
    expect(state.handoffs).toBe(0);
    expect(state.wallTimeSeconds).toBe(0);
    expect(state.stopped).toBe(false);
    expect(state.stoppedReason).toBeUndefined();
    expect(state.warnings).toEqual([]);
    expect(state.startedAt).toBeTruthy();
  });

  it("getOrCreate returns existing record on second call", () => {
    const first = store.getOrCreate("task-xyz", "qa");
    const second = store.getOrCreate("task-xyz", "qa");

    expect(second.startedAt).toBe(first.startedAt);
    expect(second.taskId).toBe("task-xyz");
  });

  it("getOrCreate does not overwrite existing record with different role", () => {
    store.getOrCreate("task-1", "coder");
    const state = store.getOrCreate("task-1", "architect"); // should return existing coder record

    expect(state.agentRole).toBe("coder");
  });

  it("incrementTokens accumulates correctly across multiple calls", () => {
    store.getOrCreate("task-tok", "coder");
    store.incrementTokens("task-tok", 1000);
    store.incrementTokens("task-tok", 2500);
    store.incrementTokens("task-tok", 500);

    const state = store.getState("task-tok");
    expect(state?.tokensUsed).toBe(4000);
  });

  it("incrementCalls increments by 1 each call", () => {
    store.getOrCreate("task-calls", "qa");
    store.incrementCalls("task-calls");
    store.incrementCalls("task-calls");
    store.incrementCalls("task-calls");

    const state = store.getState("task-calls");
    expect(state?.externalCalls).toBe(3);
  });

  it("markStopped persists stopped flag and reason", () => {
    store.getOrCreate("task-stop", "intern");
    store.markStopped("task-stop", "Exceeded token limit");

    const state = store.getState("task-stop");
    expect(state?.stopped).toBe(true);
    expect(state?.stoppedReason).toBe("Exceeded token limit");
  });

  it("addWarning accumulates warnings as an array", () => {
    store.getOrCreate("task-warn", "coder");
    store.addWarning("task-warn", "First warning");
    store.addWarning("task-warn", "Second warning");

    const state = store.getState("task-warn");
    expect(state?.warnings).toHaveLength(2);
    expect(state?.warnings[0]).toBe("First warning");
    expect(state?.warnings[1]).toBe("Second warning");
  });

  it("updateWallTime sets wall_time_seconds to a positive value", () => {
    store.getOrCreate("task-time", "system");
    store.updateWallTime("task-time");

    const state = store.getState("task-time");
    expect(state?.wallTimeSeconds).toBeGreaterThanOrEqual(0);
  });

  it("getState returns null for unknown taskId", () => {
    const state = store.getState("nonexistent-task");
    expect(state).toBeNull();
  });

  it("listActive returns only non-stopped tasks", () => {
    store.getOrCreate("task-active-1", "coder");
    store.getOrCreate("task-active-2", "qa");
    store.getOrCreate("task-stopped", "intern");
    store.markStopped("task-stopped", "limit");

    const active = store.listActive();
    const ids = active.map((s) => s.taskId);

    expect(ids).toContain("task-active-1");
    expect(ids).toContain("task-active-2");
    expect(ids).not.toContain("task-stopped");
  });

  it("setConfigOverride and getConfigOverride round-trip JSON", () => {
    const json = JSON.stringify({ agentRole: "custom", maxTokensPerTask: 9999 });
    store.setConfigOverride("custom", json);

    const retrieved = store.getConfigOverride("custom");
    expect(retrieved).toBe(json);
  });

  it("getConfigOverride returns null for unknown role", () => {
    const result = store.getConfigOverride("unknown-role");
    expect(result).toBeNull();
  });

  describe("dailyReset", () => {
    it("resets tokens_used to 0 for tasks started on a previous day", () => {
      // Insert a task backdated to yesterday
      const yesterday = new Date(Date.now() - 86_400_000).toISOString();
      db.prepare(
        `INSERT INTO budget_states
           (task_id, agent_role, tokens_used, external_calls, handoffs,
            wall_time_seconds, started_at, warnings, stopped, stopped_reason)
         VALUES ('task-old', 'coder', 500, 0, 0, 0, ?, '[]', 0, NULL)`
      ).run(yesterday);

      // Force the reset tracker to a past date so dailyReset will fire
      db.prepare(
        `INSERT OR REPLACE INTO daily_budget_reset (id, last_reset_date, last_reset_at, tokens_reset_count)
         VALUES ('singleton', '2000-01-01', '2000-01-01T00:00:00.000Z', 0)`
      ).run();

      store.dailyReset();

      const row = db
        .prepare("SELECT tokens_used FROM budget_states WHERE task_id = 'task-old'")
        .get() as { tokens_used: number };
      expect(row.tokens_used).toBe(0);
    });

    it("is idempotent — calling twice does not double-reset or error", () => {
      // Backdated task with tokens
      const yesterday = new Date(Date.now() - 86_400_000).toISOString();
      db.prepare(
        `INSERT INTO budget_states
           (task_id, agent_role, tokens_used, external_calls, handoffs,
            wall_time_seconds, started_at, warnings, stopped, stopped_reason)
         VALUES ('task-idem', 'coder', 200, 0, 0, 0, ?, '[]', 0, NULL)`
      ).run(yesterday);

      db.prepare(
        `INSERT OR REPLACE INTO daily_budget_reset (id, last_reset_date, last_reset_at, tokens_reset_count)
         VALUES ('singleton', '2000-01-01', '2000-01-01T00:00:00.000Z', 0)`
      ).run();

      store.dailyReset();
      store.dailyReset(); // second call must be a no-op

      const row = db
        .prepare("SELECT tokens_used FROM budget_states WHERE task_id = 'task-idem'")
        .get() as { tokens_used: number };
      expect(row.tokens_used).toBe(0);

      const resetRow = db
        .prepare("SELECT COUNT(*) as cnt FROM daily_budget_reset")
        .get() as { cnt: number };
      expect(resetRow.cnt).toBe(1);
    });

    it("concurrent resets at midnight are safe — exactly one reset record remains", () => {
      db.prepare(
        `INSERT OR REPLACE INTO daily_budget_reset (id, last_reset_date, last_reset_at, tokens_reset_count)
         VALUES ('singleton', '2000-01-01', '2000-01-01T00:00:00.000Z', 0)`
      ).run();

      store.dailyReset();
      store.dailyReset();

      const rows = db
        .prepare("SELECT COUNT(*) as cnt FROM daily_budget_reset")
        .get() as { cnt: number };
      expect(rows.cnt).toBe(1);
    });

    it("getTokensUsedToday returns 0 after reset clears yesterday's tasks", () => {
      const yesterday = new Date(Date.now() - 86_400_000).toISOString();
      db.prepare(
        `INSERT INTO budget_states
           (task_id, agent_role, tokens_used, external_calls, handoffs,
            wall_time_seconds, started_at, warnings, stopped, stopped_reason)
         VALUES ('task-today-check', 'coder', 100, 0, 0, 0, ?, '[]', 0, NULL)`
      ).run(yesterday);

      db.prepare(
        `INSERT OR REPLACE INTO daily_budget_reset (id, last_reset_date, last_reset_at, tokens_reset_count)
         VALUES ('singleton', '2000-01-01', '2000-01-01T00:00:00.000Z', 0)`
      ).run();

      store.dailyReset();

      // Task was from yesterday, so it's not counted in today's total
      expect(store.getTokensUsedToday()).toBe(0);
    });

    it("getTokensUsedToday accumulates tokens for tasks started today", () => {
      store.getOrCreate("task-today-a", "coder");
      store.incrementTokens("task-today-a", 300);

      store.getOrCreate("task-today-b", "qa");
      store.incrementTokens("task-today-b", 700);

      expect(store.getTokensUsedToday()).toBe(1000);
    });
  });
});
