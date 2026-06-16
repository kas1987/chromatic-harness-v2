import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { detectSessionMode, getVramProfile, safeOllamaModel } from "../../src/context/vram-guard.js";

describe("detectSessionMode", () => {
  const originalEnv = process.env.GEN_SESSION_MODE;

  afterEach(() => {
    if (originalEnv === undefined) {
      delete process.env.GEN_SESSION_MODE;
    } else {
      process.env.GEN_SESSION_MODE = originalEnv;
    }
  });

  it("returns env override when set to 'heavy'", () => {
    process.env.GEN_SESSION_MODE = "heavy";
    expect(detectSessionMode()).toBe("heavy");
  });

  it("returns env override when set to 'idle'", () => {
    process.env.GEN_SESSION_MODE = "idle";
    expect(detectSessionMode()).toBe("idle");
  });

  it("defaults to 'light' when no env var set", () => {
    delete process.env.GEN_SESSION_MODE;
    expect(detectSessionMode()).toBe("light");
  });

  it("ignores invalid env values and defaults to 'light'", () => {
    process.env.GEN_SESSION_MODE = "turbo-mode";
    expect(detectSessionMode()).toBe("light");
  });
});

describe("getVramProfile", () => {
  it("heavy mode: local LLMs disabled, planning gate disabled", () => {
    const p = getVramProfile("heavy");
    expect(p.ollamaLightSafe).toBe(false);
    expect(p.lmStudioSafe).toBe(false);
    expect(p.disablePlanningGate).toBe(true);
  });

  it("light mode: small Ollama safe, LM Studio deferred", () => {
    const p = getVramProfile("light");
    expect(p.ollamaLightSafe).toBe(true);
    expect(p.lmStudioSafe).toBe(false);
    expect(p.disablePlanningGate).toBe(false);
  });

  it("idle mode: all local inference available", () => {
    const p = getVramProfile("idle");
    expect(p.ollamaLightSafe).toBe(true);
    expect(p.lmStudioSafe).toBe(true);
    expect(p.disablePlanningGate).toBe(false);
  });

  it("heavy mode availableVramGb is non-negative", () => {
    const p = getVramProfile("heavy");
    expect(p.availableVramGb).toBeGreaterThanOrEqual(0);
  });

  it("each mode has a non-empty note", () => {
    for (const mode of ["heavy", "light", "idle"] as const) {
      expect(getVramProfile(mode).note.length).toBeGreaterThan(0);
    }
  });
});

describe("safeOllamaModel", () => {
  it("heavy mode returns smallest model (CPU-safe)", () => {
    const model = safeOllamaModel("heavy");
    expect(model).toBe("qwen3:4b");
  });

  it("light mode returns medium code model", () => {
    const model = safeOllamaModel("light");
    expect(model).toBe("qwen2.5-coder:7b");
  });

  it("idle mode returns larger code model", () => {
    const model = safeOllamaModel("idle");
    expect(model).toBe("qwen2.5-coder:14b");
  });
});
