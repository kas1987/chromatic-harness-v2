import { describe, it, expect, beforeEach } from "vitest";
import { BudgetGuard } from "../../src/core/budget-guard";
import {
  AgentId,
  ProjectId,
  UserId,
  TaskId,
  TaskPurpose,
} from "../../src/core/ids";

describe("BudgetGuard", () => {
  let guard: BudgetGuard;

  beforeEach(() => {
    guard = new BudgetGuard();
  });

  const mockContext = {
    agentId: "agent-1" as AgentId,
    agentRole: "system",
    projectId: "proj-1" as ProjectId,
    userId: "user-1" as UserId,
    trustLevel: 2 as const,
    sessionId: "sess-1",
    taskId: "task-1" as TaskId,
    purpose: "code" as TaskPurpose,
  };

  it("evaluateBashCommand should block `rm -rf /`", () => {
    const command = "rm -rf /etc/config";
    const decision = guard.evaluateBashCommand(command, mockContext);

    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Dangerous command blocked");
  });

  it("evaluateBashCommand should block `DROP TABLE`", () => {
    const command = "DROP TABLE users;";
    const decision = guard.evaluateBashCommand(command, mockContext);

    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Dangerous command blocked");
  });

  it("evaluateBashCommand should allow safe commands", () => {
    const command = "ls -la /home/user";
    const decision = guard.evaluateBashCommand(command, mockContext);

    expect(decision.continue).toBe(true);
  });

  it("evaluateFileWrite should block protected paths", () => {
    const filePath = "C:\\Windows\\System32\\config.ini";
    const decision = guard.evaluateFileWrite(filePath, mockContext);

    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Protected path blocked");
  });

  it("evaluateFileWrite should allow normal paths", () => {
    const filePath = "/home/user/project/file.ts";
    const decision = guard.evaluateFileWrite(filePath, mockContext);

    expect(decision.continue).toBe(true);
  });

  // --- git destructive operations ---

  it("evaluateBashCommand should block `git reset --hard`", () => {
    const decision = guard.evaluateBashCommand("git reset --hard HEAD~3", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Dangerous command blocked");
  });

  it("evaluateBashCommand should block `git push --force`", () => {
    const decision = guard.evaluateBashCommand("git push origin main --force", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Dangerous command blocked");
  });

  it("evaluateBashCommand should block `git push -f`", () => {
    const decision = guard.evaluateBashCommand("git push origin main -f", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Dangerous command blocked");
  });

  it("evaluateBashCommand should allow safe git operations", () => {
    const decision = guard.evaluateBashCommand("git push origin feature-branch", mockContext);
    expect(decision.continue).toBe(true);
  });

  // --- project directory wipes ---

  it("evaluateBashCommand should block `rm -rf ./` project wipe", () => {
    const decision = guard.evaluateBashCommand("rm -rf ./node_modules", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Dangerous command blocked");
  });

  it("evaluateBashCommand should block Windows `rmdir /s /q`", () => {
    const decision = guard.evaluateBashCommand("rmdir /s /q D:\\project\\src", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Dangerous command blocked");
  });

  it("evaluateBashCommand should block `find . -delete`", () => {
    const decision = guard.evaluateBashCommand("find . -name '*.tmp' -delete", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Dangerous command blocked");
  });

  // --- database schema destruction ---

  it("evaluateBashCommand should block `DROP SCHEMA`", () => {
    const decision = guard.evaluateBashCommand("DROP SCHEMA public CASCADE;", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Dangerous command blocked");
  });

  it("evaluateBashCommand should block `ALTER TABLE ... DROP COLUMN`", () => {
    const decision = guard.evaluateBashCommand("ALTER TABLE users DROP COLUMN email;", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Dangerous command blocked");
  });

  // --- infrastructure teardown ---

  it("evaluateBashCommand should block `terraform destroy`", () => {
    const decision = guard.evaluateBashCommand("terraform destroy -auto-approve", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Dangerous command blocked");
  });

  it("evaluateBashCommand should block `kubectl delete namespace`", () => {
    const decision = guard.evaluateBashCommand("kubectl delete namespace production", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Dangerous command blocked");
  });

  // --- sensitive file writes ---

  it("evaluateFileWrite should block writes to .env files", () => {
    const decision = guard.evaluateFileWrite("D:/project/.env", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Sensitive file blocked");
  });

  it("evaluateFileWrite should block writes to .env.local", () => {
    const decision = guard.evaluateFileWrite("/project/.env.local", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Sensitive file blocked");
  });

  it("evaluateFileWrite should block writes to .env.production", () => {
    const decision = guard.evaluateFileWrite("/project/.env.production", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Sensitive file blocked");
  });

  it("evaluateFileWrite should block writes to .pem files", () => {
    const decision = guard.evaluateFileWrite("/home/user/.ssh/server.pem", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Sensitive file blocked");
  });

  it("evaluateFileWrite should block writes to .key files", () => {
    const decision = guard.evaluateFileWrite("/certs/private.key", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Sensitive file blocked");
  });

  it("evaluateFileWrite should block writes to id_rsa", () => {
    const decision = guard.evaluateFileWrite("/home/user/.ssh/id_rsa", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Sensitive file blocked");
  });

  it("evaluateFileWrite should block writes to credentials.json", () => {
    const decision = guard.evaluateFileWrite("/app/credentials.json", mockContext);
    expect(decision.continue).toBe(false);
    expect(decision.stopReason).toContain("Sensitive file blocked");
  });

  it("evaluateFileWrite should allow writes to .env.example", () => {
    const decision = guard.evaluateFileWrite("/project/.env.example", mockContext);
    expect(decision.continue).toBe(true);
  });
});
