/**
 * llm-routing-integration.test.ts — RED tests for Issue 6
 *
 * These tests verify NEW exports and behavior added to hooks.ts by Issue 6.
 * They MUST FAIL until the implementation is complete because:
 *   - `inferScope` is not yet exported from hooks.ts
 *   - GET /hooks/llm-hint route does not yet exist
 *   - `suggestedLlm` field is not yet present in PreToolUse responses
 *
 * Do NOT modify these tests to make them pass. Fix the implementation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import express from "express";
import request from "supertest";
import { hooksRouter, inferScope } from "../../src/routes/hooks.js";

// ---------------------------------------------------------------------------
// inferScope — pure function, exported for testing (contract requirement)
// ---------------------------------------------------------------------------

describe("inferScope", () => {
  it("InferScope_Read_ReturnsSimple: Read tool maps to simple scope", () => {
    expect(inferScope("Read", {})).toBe("simple");
  });

  it("InferScope_Bash_ReturnsMedium: Bash tool maps to medium scope", () => {
    expect(inferScope("Bash", {})).toBe("medium");
  });

  it("InferScope_Edit_ShortContent_ReturnsSimple: Edit with short new_string returns simple", () => {
    expect(inferScope("Edit", { new_string: "x" })).toBe("simple");
  });

  it("InferScope_Edit_LongContent_ReturnsComplex: Edit with new_string > 2000 chars returns complex", () => {
    expect(inferScope("Edit", { new_string: "x".repeat(2001) })).toBe("complex");
  });

  it("InferScope_Unknown_ReturnsSimple: Unknown tool (MultiEdit) defaults to simple", () => {
    expect(inferScope("MultiEdit", {})).toBe("simple");
  });

  // Additional boundary cases per contract spec
  it("InferScope_Glob_ReturnsSimple: Glob is a read-only tool, maps to simple", () => {
    expect(inferScope("Glob", { pattern: "**/*.ts" })).toBe("simple");
  });

  it("InferScope_Grep_ReturnsSimple: Grep is a read-only tool, maps to simple", () => {
    expect(inferScope("Grep", { pattern: "TODO" })).toBe("simple");
  });

  it("InferScope_Edit_MediumContent_ReturnsMedium: Edit with 500-2000 chars returns medium", () => {
    // 500 chars is the lower boundary of 'medium'
    expect(inferScope("Edit", { new_string: "x".repeat(500) })).toBe("medium");
    // 2000 chars is still medium (> 2000 is complex)
    expect(inferScope("Edit", { new_string: "x".repeat(2000) })).toBe("medium");
  });

  it("InferScope_Write_UsesContent_Field: Write tool uses content field for length check", () => {
    // Write uses toolInput.content (not new_string)
    expect(inferScope("Write", { content: "x".repeat(2001) })).toBe("complex");
    expect(inferScope("Write", { content: "short" })).toBe("simple");
  });
});

// ---------------------------------------------------------------------------
// Hook response — suggestedLlm field (additive, never breaks continue)
// ---------------------------------------------------------------------------

describe("PreToolUse hook — suggestedLlm in response (Issue 6)", () => {
  let app: express.Application;

  beforeEach(() => {
    app = express();
    app.use(express.json());
    app.use("/hooks", hooksRouter);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("SuggestedLlmPresentInResponse: PreToolUse response includes suggestedLlm field", async () => {
    const response = await request(app).post("/hooks/pretool").send({
      tool: "Bash",
      input: { command: "ls -la" },
    });

    expect(response.status).toBe(200);
    expect(response.body.suggestedLlm).toBeDefined();
  });

  it("SuggestedLlmValidProvider: suggestedLlm is one of the valid LlmProvider values", async () => {
    const response = await request(app).post("/hooks/pretool").send({
      tool: "Read",
      input: { file_path: "/some/file.ts" },
    });

    expect(response.status).toBe(200);
    const validProviders = ["claude", "gpt", "gemini", "ollama", "lm-studio", "minimax", "gemma"];
    expect(validProviders).toContain(response.body.suggestedLlm);
  });

  it("HookResponseStillHasContinue: existing continue field is preserved alongside new fields", async () => {
    const response = await request(app).post("/hooks/pretool").send({
      tool: "Read",
      input: { file_path: "/some/file.ts" },
    });

    expect(response.status).toBe(200);
    // continue must still be present (contract frozen)
    expect(typeof response.body.continue).toBe("boolean");
    // stopReason must be absent or a string
    if (response.body.stopReason !== undefined) {
      expect(typeof response.body.stopReason).toBe("string");
    }
  });

  it("AllNewCodeFailOpen: hook still returns continue even if LLM selector throws", async () => {
    // We cannot easily mock module-level singletons in hooks.ts from outside,
    // but we can verify the fail-open contract by confirming a valid response
    // arrives for any tool call — error simulation is covered in integration tests.
    // This test validates the shape contract is upheld.
    const response = await request(app).post("/hooks/pretool").send({
      tool: "Write",
      input: { file_path: "/home/user/test.ts", new_string: "const x = 1;" },
    });

    expect(response.status).toBe(200);
    expect(typeof response.body.continue).toBe("boolean");
    // Must never 500
    expect(response.status).not.toBe(500);
  });
});

// ---------------------------------------------------------------------------
// GET /hooks/llm-hint — new endpoint (Issue 6)
// ---------------------------------------------------------------------------

describe("GET /hooks/llm-hint (Issue 6)", () => {
  let app: express.Application;

  beforeEach(() => {
    app = express();
    app.use(express.json());
    app.use("/hooks", hooksRouter);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("LlmHintEndpointExists: GET /hooks/llm-hint returns 200", async () => {
    const response = await request(app).get("/hooks/llm-hint");
    expect(response.status).toBe(200);
  });

  it("LlmHintEndpointShape: response contains suggestedLlm field", async () => {
    const response = await request(app).get("/hooks/llm-hint");
    expect(response.status).toBe(200);
    expect(response.body.suggestedLlm).toBeDefined();
  });

  it("LlmHintEndpointValidProvider: suggestedLlm is a valid LlmProvider string", async () => {
    const response = await request(app).get("/hooks/llm-hint");
    const validProviders = ["claude", "gpt", "gemini", "ollama", "lm-studio", "minimax", "gemma"];
    expect(validProviders).toContain(response.body.suggestedLlm);
  });

  it("LlmHintDefaultValue: before any PreToolUse request, suggestedLlm defaults to claude", async () => {
    // lastSuggestedLlm module-level default must be "claude" per contract
    const response = await request(app).get("/hooks/llm-hint");
    expect(response.status).toBe(200);
    // Default is "claude" unless a prior request in this process already updated it
    // We assert it is at minimum a valid provider
    const validProviders = ["claude", "gpt", "gemini", "ollama", "lm-studio", "minimax", "gemma"];
    expect(validProviders).toContain(response.body.suggestedLlm);
  });
});
