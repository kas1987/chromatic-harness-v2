import { describe, it, expect } from "vitest";
import { GEN_ATTRS } from "../../src/otel/attributes";

describe("GEN_ATTRS", () => {
  it("every value is a string", () => {
    for (const [key, value] of Object.entries(GEN_ATTRS)) {
      expect(typeof value, `${key} should be a string`).toBe("string");
    }
  });

  it("every value starts with the 'gen.' prefix", () => {
    for (const [key, value] of Object.entries(GEN_ATTRS)) {
      expect(value, `${key} should start with 'gen.'`).toMatch(/^gen\./);
    }
  });

  it("has all expected attribute keys", () => {
    const expectedKeys = [
      "AGENT_ID",
      "AGENT_ROLE",
      "PROJECT_ID",
      "TASK_ID",
      "HOOK_EVENT",
      "DECISION",
      "STOP_REASON",
      "MEMORIES_RETURNED",
      "EMBEDDING_CACHE_HIT",
      "BUDGET_ACTION",
      "TOKENS_USED",
      "MEMORY_SCOPE",
      "MEMORY_SENSITIVITY",
      "SESSION_ID",
      "WORKFLOW_ID",
      "TOOL_NAME",
      "TOOL_SUCCESS",
      "INTENT",
      "SCOPE",
      "SUGGESTED_LLM",
      "PRETOOL_ROUTING_SOURCE",
      "ACTUAL_LLM",
      "ROUTING_RECONCILIATION",
      "SESSION_ROUTING_HIT",
      "SESSION_HINT_AGE_BUCKET",
      "PROMPT_NORMALIZER_VERSION",
      "INTENT_TOOL_COHERENCE",
      "POLICY_LAYER",
      "E2E_RUN_ID",
      "E2E_TAGS",
    ];
    for (const key of expectedKeys) {
      expect(GEN_ATTRS).toHaveProperty(key);
    }
  });

  it("has no duplicate values", () => {
    const values = Object.values(GEN_ATTRS);
    const unique = new Set(values);
    expect(unique.size).toBe(values.length);
  });
});
