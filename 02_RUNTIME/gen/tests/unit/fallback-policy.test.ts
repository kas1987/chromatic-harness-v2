import { describe, it, expect } from "vitest";
import {
  FallbackPolicy,
  DEFAULT_FALLBACK_RULES,
  FALLBACK_PROVIDER,
  FALLBACK_TIER,
  FALLBACK_TIER_DEGRADED,
} from "../../src/context/fallback-policy.js";

describe("FallbackPolicy.shouldFallback", () => {
  const policy = new FallbackPolicy();

  it("IMMEDIATE triggers: unavailable → fallback on attempt 1", () => {
    expect(policy.shouldFallback("unavailable", 1)).toBe(true);
  });

  it("IMMEDIATE triggers: provider_error → fallback on attempt 1", () => {
    expect(policy.shouldFallback("provider_error", 1)).toBe(true);
  });

  it("IMMEDIATE triggers: empty_response → fallback on attempt 1", () => {
    expect(policy.shouldFallback("empty_response", 1)).toBe(true);
  });

  it("AFTER_RETRY triggers: timeout → no fallback on attempt 1 (first try)", () => {
    expect(policy.shouldFallback("timeout", 1)).toBe(false);
  });

  it("AFTER_RETRY triggers: timeout → fallback on attempt 2 (after 1 retry)", () => {
    expect(policy.shouldFallback("timeout", 2)).toBe(true);
  });

  it("AFTER_RETRY triggers: schema_invalid → no fallback on attempt 1", () => {
    expect(policy.shouldFallback("schema_invalid", 1)).toBe(false);
  });

  it("AFTER_RETRY triggers: schema_invalid → fallback on attempt 2", () => {
    expect(policy.shouldFallback("schema_invalid", 2)).toBe(true);
  });

  it("AFTER_RETRY triggers: low_confidence → fallback on attempt 2", () => {
    expect(policy.shouldFallback("low_confidence", 2)).toBe(true);
  });

  it("unknown failure reason → always fall back", () => {
    expect(policy.shouldFallback("retry_exhausted", 1)).toBe(true);
  });
});

describe("FallbackPolicy.validateResponse", () => {
  const policy = new FallbackPolicy();

  it("null → empty_response", () => {
    expect(policy.validateResponse(null)).toBe("empty_response");
  });

  it("empty string → empty_response", () => {
    expect(policy.validateResponse("")).toBe("empty_response");
  });

  it("whitespace-only → empty_response", () => {
    expect(policy.validateResponse("   \n  ")).toBe("empty_response");
  });

  it("too short (<10 chars) → empty_response", () => {
    expect(policy.validateResponse("ok")).toBe("empty_response");
  });

  it("valid response → null (no failure)", () => {
    expect(policy.validateResponse("This is a valid response from the LLM.")).toBeNull();
  });

  it("longer minimal response → null", () => {
    expect(policy.validateResponse("1234567890x")).toBeNull(); // 11 chars
  });
});

describe("FallbackPolicy.fallbackNote", () => {
  const policy = new FallbackPolicy();

  it("returns a non-empty note for all known reasons", () => {
    const reasons = DEFAULT_FALLBACK_RULES.map((r) => r.trigger);
    for (const reason of reasons) {
      expect(policy.fallbackNote(reason).length).toBeGreaterThan(0);
    }
  });

  it("returns a note for unknown reason (defensive)", () => {
    const note = policy.fallbackNote("unknown_failure" as never);
    expect(note).toContain("Unhandled");
  });
});

describe("Fallback constants", () => {
  it("FALLBACK_PROVIDER is claude (Max plan always available)", () => {
    expect(FALLBACK_PROVIDER).toBe("claude");
  });

  it("FALLBACK_TIER is sonnet (highest quality auto-select tier)", () => {
    expect(FALLBACK_TIER).toBe("sonnet");
  });

  it("FALLBACK_TIER_DEGRADED is haiku (when sonnet session-exhausted)", () => {
    expect(FALLBACK_TIER_DEGRADED).toBe("haiku");
  });
});
