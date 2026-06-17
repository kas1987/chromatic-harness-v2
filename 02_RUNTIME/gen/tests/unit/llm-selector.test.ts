import { describe, it, expect, vi, beforeEach } from "vitest";
import { LlmSelector, toProvider } from "../../src/llm/llm-selector.js";
import { LLM_CAPABILITIES, CLAUDE_MODEL_IDS } from "../../src/llm/llm-types.js";
import type { LlmTask, LlmProvider, ILlmClient } from "../../src/llm/llm-types.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTask(overrides: Partial<LlmTask> = {}): LlmTask {
  return {
    intent: "explore",
    scope: "simple",
    ...overrides,
  };
}

function makeClient(provider: LlmProvider, available = true): ILlmClient {
  return {
    provider,
    generate: vi.fn().mockResolvedValue("ok"),
    isAvailable: vi.fn().mockResolvedValue(available),
  };
}

function makeClientFactory(overrides: Partial<Record<LlmProvider, ILlmClient>> = {}): (provider: LlmProvider) => ILlmClient {
  const defaults: Record<LlmProvider, ILlmClient> = {
    claude: makeClient("claude"),
    gpt: makeClient("gpt"),
    gemini: makeClient("gemini"),
    ollama: makeClient("ollama"),
    gemma: makeClient("gemma"),
    "lm-studio": makeClient("lm-studio"),
    minimax: makeClient("minimax"),
  };
  const clients = { ...defaults, ...overrides };
  return (provider: LlmProvider) => clients[provider];
}

// ---------------------------------------------------------------------------
// toProvider() — validation guard (I-4)
// ---------------------------------------------------------------------------

describe("toProvider", () => {
  it("UnknownProvider_ToProvider_ReturnsClaude: unknown string returns 'claude'", () => {
    expect(toProvider("unknown")).toBe("claude");
    expect(toProvider("grok")).toBe("claude");
    expect(toProvider("")).toBe("claude");
    expect(toProvider("CLAUDE")).toBe("claude"); // case-sensitive
  });

  it("ValidProvider_ToProvider: known providers pass through unchanged", () => {
    expect(toProvider("gemini")).toBe("gemini");
    expect(toProvider("gpt")).toBe("gpt");
    expect(toProvider("ollama")).toBe("ollama");
    expect(toProvider("claude")).toBe("claude");
  });
});

// ---------------------------------------------------------------------------
// LLM_CAPABILITIES — imported from llm-types
// ---------------------------------------------------------------------------

describe("LLM_CAPABILITIES", () => {
  it("LLM_CAPABILITIES_Ollama_ZeroCost: ollama costPer1kInputUsd is exactly 0", () => {
    expect(LLM_CAPABILITIES["ollama"].costPer1kInputUsd).toBe(0);
  });

  it("LLM_CAPABILITIES_Ollama_ZeroCostOutput: ollama costPer1kOutputUsd is exactly 0", () => {
    expect(LLM_CAPABILITIES["ollama"].costPer1kOutputUsd).toBe(0);
  });

  it("LLM_CAPABILITIES covers all providers including minimax and gemma", () => {
    const providers: LlmProvider[] = ["claude", "gpt", "gemini", "ollama", "lm-studio", "minimax", "gemma"];
    for (const p of providers) {
      expect(LLM_CAPABILITIES[p]).toBeDefined();
    }
  });

  it("LLM_CAPABILITIES_Claude_MaxPlan_ZeroCost: claude costs 0 under Max plan routing", () => {
    // Claude is routed via Claude Code Max plan (flat subscription).
    // Per-token cost is $0 — metered API rates only apply when using ANTHROPIC_API_KEY directly.
    expect(LLM_CAPABILITIES["claude"].costPer1kInputUsd).toBe(0.0);
    expect(LLM_CAPABILITIES["claude"].costPer1kOutputUsd).toBe(0.0);
  });
});

// ---------------------------------------------------------------------------
// LlmSelector.selectBestLlm() — synchronous heuristic routing (I-1)
// ---------------------------------------------------------------------------

describe("LlmSelector.selectBestLlm", () => {
  let selector: LlmSelector;

  beforeEach(() => {
    selector = new LlmSelector(makeClientFactory(), null);
  });

  it("VisionTask_SelectsGemini: requiresVision:true returns 'gemini'", () => {
    const task = makeTask({ requiresVision: true, intent: "explore", scope: "simple" });
    expect(selector.selectBestLlm(task)).toBe("gemini");
  });

  it("CodeTask_SelectsClaude: intent:'code' with requiresCode:true returns 'claude'", () => {
    const task = makeTask({ intent: "code", scope: "simple", requiresCode: true });
    expect(selector.selectBestLlm(task)).toBe("claude");
  });

  it("BudgetLow_SmallTask_SelectsGpt: budgetConstraint:'low' with small tokens returns 'gpt'", () => {
    const task = makeTask({
      intent: "explore",
      scope: "simple",
      budgetConstraint: "low",
      estimatedInputTokens: 5000,
    });
    expect(selector.selectBestLlm(task)).toBe("gpt");
  });

  it("RequiresLocal_SelectsOllama: requiresLocal:true returns 'ollama'", () => {
    const task = makeTask({ intent: "code", scope: "simple", requiresLocal: true });
    expect(selector.selectBestLlm(task)).toBe("ollama");
  });

  it("Default_SelectsClaude: no special flags returns 'claude'", () => {
    const task = makeTask({ intent: "manage", scope: "simple" });
    expect(selector.selectBestLlm(task)).toBe("claude");
  });

  it("selectBestLlm_Vision_OverridesCode: requiresVision + requiresCode → gemini wins", () => {
    const task = makeTask({ requiresVision: true, requiresCode: true });
    // requiresLocal is not set, so vision (rule 3) fires before code
    expect(selector.selectBestLlm(task)).toBe("gemini");
  });

  it("RequiresLocal beats requiresVision when both set (rule 1 > rule 3)", () => {
    const task = makeTask({ requiresVision: true, requiresLocal: true });
    expect(selector.selectBestLlm(task)).toBe("ollama");
  });

  it("NsfwVision_SelectsOllama: requiresVision + nsfwContext routes to ollama (rule 2)", () => {
    const task = makeTask({ requiresVision: true, nsfwContext: true });
    expect(selector.selectBestLlm(task)).toBe("ollama");
  });

  it("Vision_NoNsfw_StillGemini: requiresVision without nsfwContext routes to gemini", () => {
    const task = makeTask({ requiresVision: true, nsfwContext: false });
    expect(selector.selectBestLlm(task)).toBe("gemini");
  });

  it("BudgetLow_LargeTokens_SelectsOllama: budgetConstraint:'low' with large tokens returns 'ollama'", () => {
    const task = makeTask({
      intent: "explore",
      scope: "simple",
      budgetConstraint: "low",
      estimatedInputTokens: 15000,
    });
    expect(selector.selectBestLlm(task)).toBe("ollama");
  });

  it("intent:'code' without requiresCode still selects 'claude'", () => {
    const task = makeTask({ intent: "code", scope: "complex" });
    expect(selector.selectBestLlm(task)).toBe("claude");
  });
});

// ---------------------------------------------------------------------------
// LlmSelector with performanceTracker
// ---------------------------------------------------------------------------

describe("LlmSelector.selectBestLlm with performanceTracker", () => {
  it("LearningNoOverride_InsufficientData: getBestModel returning null falls through to default", () => {
    const tracker = {
      getBestModel: vi.fn().mockReturnValue(null),
      recordSample: vi.fn(),
    };
    const selector = new LlmSelector(makeClientFactory(), tracker);
    const task = makeTask({ intent: "explore", scope: "medium" });
    // Should fall through to default (claude) without throwing
    expect(selector.selectBestLlm(task)).toBe("claude");
  });

  it("performanceTracker returns non-null override and selector uses it", () => {
    const tracker = {
      getBestModel: vi.fn().mockReturnValue("gpt" as LlmProvider),
      recordSample: vi.fn(),
    };
    const selector = new LlmSelector(makeClientFactory(), tracker);
    const task = makeTask({ intent: "explore", scope: "medium" });
    // No local/vision/budget/code flags — tracker override fires
    expect(selector.selectBestLlm(task)).toBe("gpt");
  });

  it("null performanceTracker does not cause runtime error", () => {
    const selector = new LlmSelector(makeClientFactory(), null);
    const task = makeTask({ intent: "explore", scope: "simple" });
    expect(() => selector.selectBestLlm(task)).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// LlmSelector.selectAvailableLlm() — async availability probing (I-2, I-3)
// ---------------------------------------------------------------------------

describe("LlmSelector.selectAvailableLlm", () => {
  it("AllProvidersUnavailable_FallsBackToOllama: returns 'ollama' unconditionally when all unavailable", async () => {
    const factory = makeClientFactory({
      claude: makeClient("claude", false),
      gpt: makeClient("gpt", false),
      gemini: makeClient("gemini", false),
      minimax: makeClient("minimax", false),
      "lm-studio": makeClient("lm-studio", false),
      ollama: makeClient("ollama", false),
      gemma: makeClient("gemma", false),
    });
    const selector = new LlmSelector(factory, null);
    const task = makeTask({ intent: "code", scope: "simple" });
    const result = await selector.selectAvailableLlm(task);
    expect(result).toBe("ollama");
  });

  it("returns preferred provider when it is available", async () => {
    const factory = makeClientFactory();
    const selector = new LlmSelector(factory, null);
    const task = makeTask({ intent: "code", scope: "simple" });
    // code task → preferred = 'claude', which is available
    const result = await selector.selectAvailableLlm(task);
    expect(result).toBe("claude");
  });

  it("falls back when preferred is unavailable", async () => {
    const factory = makeClientFactory({
      claude: makeClient("claude", false),
      gpt: makeClient("gpt", true),
    });
    const selector = new LlmSelector(factory, null);
    const task = makeTask({ intent: "code", scope: "simple" });
    // claude preferred but unavailable → fallback chain → gpt
    const result = await selector.selectAvailableLlm(task);
    expect(result).toBe("gpt");
  });

  it("TTL cache: second call within 30s does not re-probe same provider", async () => {
    const claudeClient = makeClient("claude", true);
    const factory = makeClientFactory({ claude: claudeClient });
    const selector = new LlmSelector(factory, null);
    const task = makeTask({ intent: "code", scope: "simple" });

    await selector.selectAvailableLlm(task);
    await selector.selectAvailableLlm(task);

    // isAvailable on claude should have been called exactly once (TTL cache hit on second call)
    expect(claudeClient.isAvailable).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// LlmSelector.selectClaudeTier() — model tier routing (budget-aware)
// ---------------------------------------------------------------------------

describe("LlmSelector.selectClaudeTier", () => {
  let selector: LlmSelector;

  beforeEach(() => {
    selector = new LlmSelector(makeClientFactory(), null);
  });

  it("SimpleScope_SelectsHaiku: simple tasks route to haiku (no session budget pressure)", () => {
    const task = makeTask({ intent: "explore", scope: "simple" });
    expect(selector.selectClaudeTier(task)).toBe("haiku");
  });

  it("MediumScope_SelectsSonnet: medium tasks route to sonnet", () => {
    const task = makeTask({ intent: "code", scope: "medium" });
    expect(selector.selectClaudeTier(task)).toBe("sonnet");
  });

  it("ComplexScope_SelectsSonnet: complex tasks route to sonnet (never auto-escalate to opus)", () => {
    const task = makeTask({ intent: "code", scope: "complex" });
    expect(selector.selectClaudeTier(task)).toBe("sonnet");
  });

  it("ExplicitTierOverride_ReturnsOverride: claudeModelTier on task overrides scope default", () => {
    const task = makeTask({ scope: "simple", claudeModelTier: "sonnet" });
    expect(selector.selectClaudeTier(task)).toBe("sonnet");
  });

  it("CLAUDE_MODEL_IDS_Haiku_HasCorrectModelId", () => {
    expect(CLAUDE_MODEL_IDS.haiku).toBe("claude-haiku-4-5-20251001");
  });

  it("CLAUDE_MODEL_IDS_Sonnet_HasCorrectModelId", () => {
    expect(CLAUDE_MODEL_IDS.sonnet).toBe("claude-sonnet-4-6");
  });
});
