import { describe, it, expect, beforeEach } from "vitest";
import { normalizeIntent, ghostIntake } from "../ghost/ghost-intake";
import { RawRequestEnvelope } from "../ghost/ghost-types";

describe("Ghost Intake Normalizer", () => {
  let now: string;

  beforeEach(() => {
    now = new Date().toISOString();
    ghostIntake.clearCache();
  });

  const createEnvelope = (rawInput: string, overrides?: Partial<RawRequestEnvelope>): RawRequestEnvelope => ({
    requestId: `req-${Date.now()}`,
    rawInput,
    source: "claude_cli",
    sessionId: "sess-test",
    timestamp: now,
    ...overrides,
  });

  describe("Intent Classification", () => {
    it("classifies debug intent correctly", () => {
      const input = "can you unpack and we /rpi the Inject system";
      const intent = normalizeIntent(createEnvelope(input));
      expect(intent.primary_intent).toBe("debug");
      expect(intent.confidence).toBeGreaterThan(0.7);
      expect(intent.explicit_keywords).toContain("unpack");
    });

    it("classifies code intent correctly", () => {
      const input = "write a function to validate the configuration";
      const intent = normalizeIntent(createEnvelope(input));
      expect(intent.primary_intent).toBe("code");
      expect(intent.confidence).toBeGreaterThan(0.7);
      expect(intent.explicit_keywords).toContain("write");
    });

    it("classifies generation intent correctly", () => {
      const input = "generate a batch of 100 images with the checkpoint PR23";
      const intent = normalizeIntent(createEnvelope(input));
      expect(intent.primary_intent).toBe("generation");
      expect(intent.confidence).toBeGreaterThan(0.7);
      expect(intent.explicit_keywords).toContain("generate");
      expect(intent.explicit_keywords).toContain("batch");
    });
  });

  describe("Scope Determination", () => {
    it("classifies simple scope for short requests", () => {
      const input = "fix the bug";
      const intent = normalizeIntent(createEnvelope(input));
      expect(intent.scope).toBe("simple");
    });

    it("classifies complex scope for batch operations", () => {
      const input = "batch process all 10000 records in parallel loops";
      const intent = normalizeIntent(createEnvelope(input));
      expect(intent.scope).toBe("complex");
    });
  });

  describe("Risk Detection", () => {
    it("detects dangerous command patterns", () => {
      const input = "execute rm -rf /some/path";
      const intent = normalizeIntent(createEnvelope(input));
      expect(intent.risk_markers.length).toBeGreaterThan(0);
      expect(intent.requires_policy_review).toBe(true);
    });

    it("detects protected path access", () => {
      const input = "modify the .env file";
      const intent = normalizeIntent(createEnvelope(input));
      expect(intent.risk_markers.length).toBeGreaterThan(0);
    });

    it("allows safe requests", () => {
      const input = "can you explain how the system works?";
      const intent = normalizeIntent(createEnvelope(input));
      expect(intent.risk_markers.length).toBe(0);
    });
  });

  describe("Canonical Intent Structure", () => {
    it("includes all required fields", () => {
      const input = "fix the bug";
      const intent = normalizeIntent(createEnvelope(input));
      expect(intent.intentId).toBeDefined();
      expect(intent.primary_intent).toBeDefined();
      expect(intent.scope).toBeDefined();
      expect(intent.explicit_keywords).toBeDefined();
      expect(intent.ambiguity_level).toBeDefined();
      expect(intent.confidence).toBeDefined();
      expect(intent.sessionId).toBeDefined();
      expect(intent.timestamp).toBeDefined();
    });
  });

  describe("GhostIntake Service", () => {
    it("processes requests correctly", () => {
      const envelope = createEnvelope("can you unpack the system?");
      const intent = ghostIntake.process(envelope);
      expect(intent.primary_intent).toBe("debug");
    });

    it("caches results", () => {
      const envelope = createEnvelope("test");
      const intent1 = ghostIntake.process(envelope);
      const intent2 = ghostIntake.process(envelope);
      expect(intent1).toEqual(intent2);
    });
  });
});
