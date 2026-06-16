import { describe, it, expect } from "vitest";
import { intentToRoutingHints, toProvider, LlmSelector } from "../llm-selector.js";
import type { IntentClass } from "../../prompting/prompt-normalizer.js";
import type { LlmProvider, LlmTask, ILlmClient } from "../llm-types.js";

describe("intentToRoutingHints", () => {
  it('returns Ollama routing for "explore"', () => {
    const hints = intentToRoutingHints("explore");
    expect(hints).toEqual({ requiresLocal: true, requiresCode: false });
  });

  it('returns Ollama routing for "status"', () => {
    const hints = intentToRoutingHints("status");
    expect(hints).toEqual({ requiresLocal: true, requiresCode: false });
  });

  it('returns Ollama routing for "manage"', () => {
    const hints = intentToRoutingHints("manage");
    expect(hints).toEqual({ requiresLocal: true, requiresCode: false });
  });

  it('returns Ollama routing for "trigger"', () => {
    const hints = intentToRoutingHints("trigger");
    expect(hints).toEqual({ requiresLocal: true, requiresCode: false });
  });

  it('returns Ollama routing for "schedule"', () => {
    const hints = intentToRoutingHints("schedule");
    expect(hints).toEqual({ requiresLocal: true, requiresCode: false });
  });

  it('returns Claude routing for "code"', () => {
    const hints = intentToRoutingHints("code");
    expect(hints).toEqual({ requiresLocal: false, requiresCode: true });
  });

  it('returns Claude routing for "dispatch"', () => {
    const hints = intentToRoutingHints("dispatch");
    expect(hints).toEqual({ requiresLocal: false, requiresCode: true });
  });

  it("covers all 7 IntentClass values", () => {
    const allIntents: IntentClass[] = ["code", "explore", "manage", "status", "dispatch", "trigger", "schedule"];
    expect(allIntents).toHaveLength(7);

    for (const intent of allIntents) {
      const hints = intentToRoutingHints(intent);
      expect(hints).toHaveProperty("requiresLocal");
      expect(hints).toHaveProperty("requiresCode");
      // Mutually exclusive: routing to Ollama means not requiresCode, and vice versa
      expect(hints.requiresLocal).toBe(!hints.requiresCode);
    }
  });

  it("Ollama intents have requiresLocal=true and requiresCode=false", () => {
    const ollamaIntents: IntentClass[] = ["explore", "status", "manage", "trigger", "schedule"];
    for (const intent of ollamaIntents) {
      const hints = intentToRoutingHints(intent);
      expect(hints.requiresLocal).toBe(true);
      expect(hints.requiresCode).toBe(false);
    }
  });

  it("Claude intents have requiresLocal=false and requiresCode=true", () => {
    const claudeIntents: IntentClass[] = ["code", "dispatch"];
    for (const intent of claudeIntents) {
      const hints = intentToRoutingHints(intent);
      expect(hints.requiresLocal).toBe(false);
      expect(hints.requiresCode).toBe(true);
    }
  });
});

describe("toProvider — MiniMax registration", () => {
  it('recognizes "minimax" as a valid provider', () => {
    expect(toProvider("minimax")).toBe("minimax");
  });

  it('returns "claude" for unknown providers (safe default)', () => {
    expect(toProvider("unknown-llm")).toBe("claude");
    expect(toProvider("")).toBe("claude");
  });

  it('still recognizes all original providers', () => {
    const originals: LlmProvider[] = ["claude", "gpt", "gemini", "ollama", "lm-studio", "minimax", "gemma"];
    for (const p of originals) {
      expect(toProvider(p)).toBe(p);
    }
  });
});

describe("LlmSelector.selectBestLlm — MiniMax large-context routing", () => {
  // Minimal stub factory: returns a client whose isAvailable() never gets called in selectBestLlm (sync)
  function makeSelector(): LlmSelector {
    const stubFactory = (_p: LlmProvider): ILlmClient => ({
      provider: _p,
      generate: async () => "",
      isAvailable: async () => false,
    });
    return new LlmSelector(stubFactory as any);
  }

  it("routes large-context task (>50K tokens) to minimax", () => {
    const selector = makeSelector();
    const task: LlmTask = {
      intent: "explore",
      scope: "complex",
      estimatedInputTokens: 60_000,
      requiresLocal: false,
    };
    expect(selector.selectBestLlm(task)).toBe("minimax");
  });

  it("requiresLocal=true overrides large-context rule → ollama", () => {
    const selector = makeSelector();
    const task: LlmTask = {
      intent: "explore",
      scope: "complex",
      estimatedInputTokens: 60_000,
      requiresLocal: true,
    };
    expect(selector.selectBestLlm(task)).toBe("ollama");
  });

  it("small task (<50K tokens) does not route to minimax", () => {
    const selector = makeSelector();
    const task: LlmTask = {
      intent: "explore",
      scope: "simple",
      estimatedInputTokens: 10_000,
    };
    // explore → requiresLocal=false here (we're testing selectBestLlm directly, not via intent hints)
    // Small token count → falls through to claude (default)
    expect(selector.selectBestLlm(task)).not.toBe("minimax");
  });

  it("budget=low + large tokens still routes to ollama (budget wins over context size)", () => {
    const selector = makeSelector();
    const task: LlmTask = {
      intent: "explore",
      scope: "simple",
      budgetConstraint: "low",
      estimatedInputTokens: 80_000,
    };
    expect(selector.selectBestLlm(task)).toBe("ollama");
  });

  it("exactly 50K tokens does NOT trigger minimax (threshold is >50K, not ≥50K)", () => {
    const selector = makeSelector();
    const task: LlmTask = {
      intent: "explore",
      scope: "complex",
      estimatedInputTokens: 50_000,
    };
    expect(selector.selectBestLlm(task)).not.toBe("minimax");
  });
});

describe("LlmSelector.selectBestLlm — NSFW vision routing", () => {
  function makeSelector(): LlmSelector {
    const stubFactory = (_p: LlmProvider): ILlmClient => ({
      provider: _p,
      generate: async () => "",
      isAvailable: async () => false,
    });
    return new LlmSelector(stubFactory as any);
  }

  it("NsfwVision_SelectsOllama: requiresVision + nsfwContext routes to ollama", () => {
    const selector = makeSelector();
    const task: LlmTask = {
      intent: "explore",
      scope: "simple",
      requiresVision: true,
      nsfwContext: true,
    };
    expect(selector.selectBestLlm(task)).toBe("ollama");
  });

  it("Vision_NoNsfw_SelectsGemini: requiresVision without nsfwContext routes to gemini (unchanged)", () => {
    const selector = makeSelector();
    const task: LlmTask = {
      intent: "explore",
      scope: "simple",
      requiresVision: true,
      nsfwContext: false,
    };
    expect(selector.selectBestLlm(task)).toBe("gemini");
  });

  it("Vision_NsfwUndefined_SelectsGemini: requiresVision with nsfwContext=undefined routes to gemini", () => {
    const selector = makeSelector();
    const task: LlmTask = {
      intent: "explore",
      scope: "simple",
      requiresVision: true,
    };
    expect(selector.selectBestLlm(task)).toBe("gemini");
  });

  it("NsfwVision_OverridesCode: requiresVision + nsfwContext + requiresCode → ollama wins", () => {
    const selector = makeSelector();
    const task: LlmTask = {
      intent: "code",
      scope: "complex",
      requiresVision: true,
      requiresCode: true,
      nsfwContext: true,
    };
    expect(selector.selectBestLlm(task)).toBe("ollama");
  });

  it("RequiresLocal_BeatsNsfwVision: requiresLocal takes priority over nsfw vision (rule 1 > rule 2)", () => {
    const selector = makeSelector();
    const task: LlmTask = {
      intent: "explore",
      scope: "simple",
      requiresLocal: true,
      requiresVision: true,
      nsfwContext: true,
    };
    // Both route to ollama, but requiresLocal (rule 1) fires first — behavior identical
    expect(selector.selectBestLlm(task)).toBe("ollama");
  });

  it("NsfwContext_NoVision_DoesNotRouteToOllama: nsfwContext alone does not trigger vision routing", () => {
    const selector = makeSelector();
    const task: LlmTask = {
      intent: "code",
      scope: "medium",
      nsfwContext: true,
    };
    // nsfwContext without requiresVision → falls through to code rule → claude
    expect(selector.selectBestLlm(task)).toBe("claude");
  });
});
