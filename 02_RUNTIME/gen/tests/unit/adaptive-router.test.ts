import { describe, it, expect, beforeEach } from "vitest";
import Database from "better-sqlite3";
import { LearningStore } from "../../src/learning/learning-store";
import { AdaptiveRouter, inferIntent } from "../../src/learning/adaptive-router";

function makeRouter(): { store: LearningStore; router: AdaptiveRouter } {
  const db = new Database(":memory:");
  const store = new LearningStore(db);
  const router = new AdaptiveRouter(store);
  return { store, router };
}

// ---------------------------------------------------------------------------
// inferIntent
// ---------------------------------------------------------------------------

describe("inferIntent", () => {
  it("maps Bash + npm test to run_tests", () => {
    expect(inferIntent("Bash", { command: "npm test" })).toBe("run_tests");
    expect(inferIntent("Bash", { command: "npm run test" })).toBe("run_tests");
    expect(inferIntent("Bash", { command: "npx vitest" })).toBe("run_tests");
  });

  it("maps Bash + git commit to git_commit", () => {
    expect(inferIntent("Bash", { command: "git commit -m 'fix'" })).toBe(
      "git_commit",
    );
  });

  it("maps Bash + git <other> to git_operation", () => {
    expect(inferIntent("Bash", { command: "git status" })).toBe("git_operation");
    expect(inferIntent("Bash", { command: "git push origin main" })).toBe(
      "git_operation",
    );
  });

  it("maps Bash + npm <non-test> to npm_operation", () => {
    expect(inferIntent("Bash", { command: "npm install" })).toBe("npm_operation");
    expect(inferIntent("Bash", { command: "npm run build" })).toBe(
      "npm_operation",
    );
  });

  it("maps Bash + other command to bash_command", () => {
    expect(inferIntent("Bash", { command: "ls -la" })).toBe("bash_command");
    expect(inferIntent("Bash", {})).toBe("bash_command");
  });

  it("maps Edit to edit_file", () => {
    expect(inferIntent("Edit", { file_path: "/foo/bar.ts" })).toBe("edit_file");
  });

  it("maps MultiEdit to edit_file", () => {
    expect(inferIntent("MultiEdit", {})).toBe("edit_file");
  });

  it("maps Write to write_file", () => {
    expect(inferIntent("Write", { file_path: "/foo/bar.ts" })).toBe("write_file");
  });

  it("maps Glob to search_files", () => {
    expect(inferIntent("Glob", { pattern: "**/*.ts" })).toBe("search_files");
  });

  it("maps Grep to search_content", () => {
    expect(inferIntent("Grep", { pattern: "TODO" })).toBe("search_content");
  });

  it("maps Read to read_file", () => {
    expect(inferIntent("Read", { file_path: "/foo/bar.ts" })).toBe("read_file");
  });

  it("maps WebFetch to web_fetch", () => {
    expect(inferIntent("WebFetch", { url: "https://example.com" })).toBe(
      "web_fetch",
    );
  });

  it("maps unknown tools to tool_use", () => {
    expect(inferIntent("SomeFutureTool", {})).toBe("tool_use");
  });
});

// ---------------------------------------------------------------------------
// AdaptiveRouter.recommend
// ---------------------------------------------------------------------------

describe("AdaptiveRouter.recommend", () => {
  let store: LearningStore;
  let router: AdaptiveRouter;

  beforeEach(() => {
    ({ store, router } = makeRouter());
  });

  // -----------------------------------------------------------------------
  // No data
  // -----------------------------------------------------------------------

  it('returns "No data yet" recommendation when no pattern exists', () => {
    const rec = router.recommend("coder", "Edit", { file_path: "foo.ts" });
    expect(rec.confidence).toBe(0);
    expect(rec.reason).toContain("No data yet");
    expect(rec.suggestedTool).toBeUndefined();
    expect(rec.warningMessage).toBeUndefined();
  });

  // -----------------------------------------------------------------------
  // High failure rate (< 0.3)
  // -----------------------------------------------------------------------

  it("returns a warningMessage when pattern successRate < 0.3", () => {
    // Seed 5 outcomes — 1 success, 4 failures
    const outcomes = [
      { succeeded: true },
      { succeeded: false },
      { succeeded: false },
      { succeeded: false },
      { succeeded: false },
    ];
    for (const o of outcomes) {
      store.recordOutcome({
        taskId: "t",
        agentRole: "coder",
        projectId: "p",
        intent: "bash_command",
        toolUsed: "Bash",
        succeeded: o.succeeded,
        durationMs: 50,
        tokensUsed: 5,
      });
    }
    store.computeAndStorePattern("coder", "bash_command");

    const rec = router.recommend("coder", "Bash", { command: "ls" });
    expect(rec.warningMessage).toBeTruthy();
    expect(rec.suggestedTool).toBeUndefined();
    expect(rec.confidence).toBeLessThan(0.3);
  });

  // -----------------------------------------------------------------------
  // High success rate (>= 0.7)
  // -----------------------------------------------------------------------

  it("returns suggestedTool when pattern successRate >= 0.7", () => {
    // Seed 5 outcomes — 4 successes with Edit
    const outcomes = [
      { succeeded: true },
      { succeeded: true },
      { succeeded: true },
      { succeeded: true },
      { succeeded: false },
    ];
    for (const o of outcomes) {
      store.recordOutcome({
        taskId: "t",
        agentRole: "coder",
        projectId: "p",
        intent: "edit_file",
        toolUsed: "Edit",
        succeeded: o.succeeded,
        durationMs: 100,
        tokensUsed: 10,
      });
    }
    store.computeAndStorePattern("coder", "edit_file");

    const rec = router.recommend("coder", "Edit", { file_path: "bar.ts" });
    expect(rec.suggestedTool).toBe("Edit");
    expect(rec.confidence).toBeGreaterThanOrEqual(0.7);
    expect(rec.warningMessage).toBeUndefined();
  });

  // -----------------------------------------------------------------------
  // Mixed (0.3 <= successRate < 0.7)
  // -----------------------------------------------------------------------

  it("returns neutral recommendation for mixed success rate", () => {
    const outcomes = [
      { succeeded: true },
      { succeeded: true },
      { succeeded: false },
      { succeeded: false },
      { succeeded: true },
    ];
    for (const o of outcomes) {
      store.recordOutcome({
        taskId: "t",
        agentRole: "qa",
        projectId: "p",
        intent: "run_tests",
        toolUsed: "Bash",
        succeeded: o.succeeded,
        durationMs: 300,
        tokensUsed: 30,
      });
    }
    store.computeAndStorePattern("qa", "run_tests");

    const rec = router.recommend("qa", "Bash", { command: "npm test" });
    expect(rec.suggestedTool).toBeUndefined();
    expect(rec.warningMessage).toBeUndefined();
    expect(rec.confidence).toBeGreaterThanOrEqual(0.3);
    expect(rec.confidence).toBeLessThan(0.7);
  });

  // -----------------------------------------------------------------------
  // agentRole isolation
  // -----------------------------------------------------------------------

  it("does not mix patterns across different agentRoles", () => {
    // Architect has a pattern; coder does not
    for (let i = 0; i < 4; i++) {
      store.recordOutcome({
        taskId: "t",
        agentRole: "architect",
        projectId: "p",
        intent: "read_file",
        toolUsed: "Read",
        succeeded: true,
        durationMs: 10,
        tokensUsed: 1,
      });
    }
    store.computeAndStorePattern("architect", "read_file");

    const rec = router.recommend("coder", "Read", { file_path: "x.ts" });
    expect(rec.confidence).toBe(0);
    expect(rec.reason).toContain("No data yet");
  });
});
