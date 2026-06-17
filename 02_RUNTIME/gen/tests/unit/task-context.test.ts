import { describe, it, expect } from "vitest";
import { createTaskContext, buildDelegationPrompt } from "../../src/context/task-context.js";
import type { TaskContext } from "../../src/context/task-context.js";

function makeCtx(overrides: Partial<Omit<TaskContext, "traceId" | "createdAt">> = {}): TaskContext {
  return createTaskContext({
    originalPrompt: "Refactor the auth module to use JWT instead of session cookies",
    toolName: "Edit",
    intentClass: "code",
    scopeLevel: "medium",
    selectedProvider: "claude",
    selectedModel: "claude-sonnet-4-6",
    claudeTier: "sonnet",
    ...overrides,
  });
}

describe("createTaskContext", () => {
  it("generates a unique traceId on each call", () => {
    const a = makeCtx();
    const b = makeCtx();
    expect(a.traceId).not.toBe(b.traceId);
  });

  it("traceId is 12 characters", () => {
    const ctx = makeCtx();
    expect(ctx.traceId).toHaveLength(12);
  });

  it("createdAt is a valid ISO-8601 string", () => {
    const ctx = makeCtx();
    expect(() => new Date(ctx.createdAt)).not.toThrow();
    expect(new Date(ctx.createdAt).toISOString()).toBe(ctx.createdAt);
  });

  it("preserves originalPrompt verbatim", () => {
    const prompt = "original user request — never modify this";
    const ctx = makeCtx({ originalPrompt: prompt });
    expect(ctx.originalPrompt).toBe(prompt);
  });
});

describe("buildDelegationPrompt", () => {
  it("always includes the original prompt verbatim at the top", () => {
    const ctx = makeCtx({ originalPrompt: "verbatim user request" });
    const prompt = buildDelegationPrompt(ctx);
    expect(prompt).toContain("ORIGINAL REQUEST:\nverbatim user request");
  });

  it("includes Claude elevation when set", () => {
    const ctx = makeCtx({
      claudeElevation: "This codebase uses Express v5 and Zod for validation.",
    });
    const prompt = buildDelegationPrompt(ctx);
    expect(prompt).toContain("CONTEXT:");
    expect(prompt).toContain("Express v5");
  });

  it("omits CONTEXT section when no elevation", () => {
    const ctx = makeCtx({ claudeElevation: undefined });
    const prompt = buildDelegationPrompt(ctx);
    expect(prompt).not.toContain("CONTEXT:");
  });

  it("includes constraints as bullet list", () => {
    const ctx = makeCtx({
      constraints: ["Do not modify tests", "Keep existing API surface"],
    });
    const prompt = buildDelegationPrompt(ctx);
    expect(prompt).toContain("CONSTRAINTS:");
    expect(prompt).toContain("- Do not modify tests");
    expect(prompt).toContain("- Keep existing API surface");
  });

  it("includes TASK section when delegatedTask differs from originalPrompt", () => {
    const ctx = makeCtx({
      originalPrompt: "Refactor auth module",
      delegatedTask: "Extract the session handling into a separate service",
    });
    const prompt = buildDelegationPrompt(ctx);
    expect(prompt).toContain("TASK:");
    expect(prompt).toContain("Extract the session handling");
  });

  it("omits TASK section when delegatedTask equals originalPrompt", () => {
    const original = "Do the thing";
    const ctx = makeCtx({ originalPrompt: original, delegatedTask: original });
    const prompt = buildDelegationPrompt(ctx);
    expect(prompt).not.toContain("TASK:");
  });

  it("includes OUTPUT FORMAT when set", () => {
    const ctx = makeCtx({ expectedOutputFormat: '{"files": string[], "summary": string}' });
    const prompt = buildDelegationPrompt(ctx);
    expect(prompt).toContain("OUTPUT FORMAT:");
    expect(prompt).toContain('"files"');
  });

  it("separates sections with --- dividers", () => {
    const ctx = makeCtx({ claudeElevation: "some context" });
    const prompt = buildDelegationPrompt(ctx);
    expect(prompt).toContain("---");
  });
});
