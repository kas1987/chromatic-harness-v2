import { describe, it, expect, beforeEach } from "vitest";
import Database from "better-sqlite3";
import { LearningStore } from "../../src/learning/learning-store";

function makeStore(): LearningStore {
  const db = new Database(":memory:");
  return new LearningStore(db);
}

describe("LearningStore", () => {
  let store: LearningStore;

  beforeEach(() => {
    store = makeStore();
  });

  // -------------------------------------------------------------------------
  // recordOutcome
  // -------------------------------------------------------------------------

  it("recordOutcome creates a record with generated id and recordedAt", () => {
    const outcome = store.recordOutcome({
      taskId: "task-1",
      agentRole: "coder",
      projectId: "proj-1",
      intent: "edit_file",
      toolUsed: "Edit",
      succeeded: true,
      durationMs: 120,
      tokensUsed: 30,
    });

    expect(outcome.id).toBeTruthy();
    expect(outcome.recordedAt).toBeTruthy();
    expect(new Date(outcome.recordedAt).getTime()).toBeGreaterThan(0);
    expect(outcome.taskId).toBe("task-1");
    expect(outcome.agentRole).toBe("coder");
    expect(outcome.intent).toBe("edit_file");
    expect(outcome.toolUsed).toBe("Edit");
    expect(outcome.succeeded).toBe(true);
    expect(outcome.durationMs).toBe(120);
    expect(outcome.tokensUsed).toBe(30);
    expect(outcome.errorMessage).toBeUndefined();
  });

  it("recordOutcome stores errorMessage when provided", () => {
    const outcome = store.recordOutcome({
      taskId: "task-2",
      agentRole: "coder",
      projectId: "proj-1",
      intent: "bash_command",
      toolUsed: "Bash",
      succeeded: false,
      durationMs: 50,
      tokensUsed: 5,
      errorMessage: "command not found",
    });

    expect(outcome.succeeded).toBe(false);
    expect(outcome.errorMessage).toBe("command not found");
  });

  // -------------------------------------------------------------------------
  // getOutcomesForIntent
  // -------------------------------------------------------------------------

  it("getOutcomesForIntent returns outcomes in descending recorded_at order", async () => {
    for (let i = 0; i < 3; i++) {
      store.recordOutcome({
        taskId: `task-${i}`,
        agentRole: "coder",
        projectId: "proj-1",
        intent: "edit_file",
        toolUsed: "Edit",
        succeeded: i < 2,
        durationMs: 100 + i * 10,
        tokensUsed: 10,
      });
      // Tiny pause so recorded_at values differ (SQLite TEXT comparison)
      await new Promise((r) => setTimeout(r, 5));
    }

    const outcomes = store.getOutcomesForIntent("coder", "edit_file");
    expect(outcomes.length).toBe(3);
    // Most recent first
    for (let i = 0; i < outcomes.length - 1; i++) {
      expect(outcomes[i].recordedAt >= outcomes[i + 1].recordedAt).toBe(true);
    }
  });

  it("getOutcomesForIntent respects the limit parameter", () => {
    for (let i = 0; i < 5; i++) {
      store.recordOutcome({
        taskId: `task-${i}`,
        agentRole: "qa",
        projectId: "proj-1",
        intent: "run_tests",
        toolUsed: "Bash",
        succeeded: true,
        durationMs: 200,
        tokensUsed: 20,
      });
    }
    const outcomes = store.getOutcomesForIntent("qa", "run_tests", 3);
    expect(outcomes.length).toBe(3);
  });

  it("getOutcomesForIntent does not return outcomes for a different agentRole or intent", () => {
    store.recordOutcome({
      taskId: "task-x",
      agentRole: "architect",
      projectId: "proj-1",
      intent: "read_file",
      toolUsed: "Read",
      succeeded: true,
      durationMs: 10,
      tokensUsed: 1,
    });

    expect(store.getOutcomesForIntent("coder", "read_file")).toHaveLength(0);
    expect(store.getOutcomesForIntent("architect", "edit_file")).toHaveLength(0);
  });

  // -------------------------------------------------------------------------
  // computeAndStorePattern — insufficient samples
  // -------------------------------------------------------------------------

  it("computeAndStorePattern returns null when fewer than 3 samples", () => {
    store.recordOutcome({
      taskId: "t1",
      agentRole: "coder",
      projectId: "p",
      intent: "edit_file",
      toolUsed: "Edit",
      succeeded: true,
      durationMs: 100,
      tokensUsed: 10,
    });
    store.recordOutcome({
      taskId: "t2",
      agentRole: "coder",
      projectId: "p",
      intent: "edit_file",
      toolUsed: "Edit",
      succeeded: true,
      durationMs: 100,
      tokensUsed: 10,
    });

    const result = store.computeAndStorePattern("coder", "edit_file");
    expect(result).toBeNull();
  });

  // -------------------------------------------------------------------------
  // computeAndStorePattern — correct aggregation
  // -------------------------------------------------------------------------

  it("computeAndStorePattern computes correct successRate and preferredTool", () => {
    // 2 successes with "Edit", 1 failure with "MultiEdit"
    const outcomes = [
      { toolUsed: "Edit", succeeded: true },
      { toolUsed: "Edit", succeeded: true },
      { toolUsed: "MultiEdit", succeeded: false },
    ];

    for (const o of outcomes) {
      store.recordOutcome({
        taskId: "task-x",
        agentRole: "coder",
        projectId: "proj-1",
        intent: "edit_file",
        toolUsed: o.toolUsed,
        succeeded: o.succeeded,
        durationMs: 100,
        tokensUsed: 10,
      });
    }

    const pattern = store.computeAndStorePattern("coder", "edit_file");

    expect(pattern).not.toBeNull();
    // 2 out of 3 succeeded overall
    expect(pattern!.successRate).toBeCloseTo(2 / 3);
    // Edit has 2/2 success rate vs MultiEdit's 0/1 — Edit should be preferred
    expect(pattern!.preferredTool).toBe("Edit");
    expect(pattern!.sampleCount).toBe(3);
    expect(pattern!.agentRole).toBe("coder");
    expect(pattern!.intent).toBe("edit_file");
  });

  it("computeAndStorePattern picks tool with highest per-tool success rate", () => {
    // Bash: 3/3 successes, Edit: 1/1 success but fewer samples
    const outcomes = [
      { toolUsed: "Bash", succeeded: true },
      { toolUsed: "Bash", succeeded: true },
      { toolUsed: "Bash", succeeded: true },
      { toolUsed: "Edit", succeeded: true },
    ];

    for (const o of outcomes) {
      store.recordOutcome({
        taskId: "t",
        agentRole: "coder",
        projectId: "p",
        intent: "bash_command",
        toolUsed: o.toolUsed,
        succeeded: o.succeeded,
        durationMs: 50,
        tokensUsed: 5,
      });
    }

    const pattern = store.computeAndStorePattern("coder", "bash_command");
    expect(pattern).not.toBeNull();
    // Both have 100 % success rate; Bash wins on sample count
    expect(pattern!.preferredTool).toBe("Bash");
  });

  it("computeAndStorePattern is idempotent — running twice yields same result", () => {
    for (let i = 0; i < 4; i++) {
      store.recordOutcome({
        taskId: `t${i}`,
        agentRole: "coder",
        projectId: "p",
        intent: "write_file",
        toolUsed: "Write",
        succeeded: true,
        durationMs: 80,
        tokensUsed: 8,
      });
    }

    const first = store.computeAndStorePattern("coder", "write_file");
    const second = store.computeAndStorePattern("coder", "write_file");

    expect(first).not.toBeNull();
    expect(second).not.toBeNull();
    // id should be stable across upserts
    expect(first!.id).toBe(second!.id);
    expect(first!.successRate).toBe(second!.successRate);
  });
});
