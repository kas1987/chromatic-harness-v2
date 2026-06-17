import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import type { LlmProvider } from "../../src/llm/llm-types.js";

// ---------------------------------------------------------------------------
// Module mocks — declared before dynamic import so vi.mock hoisting applies.
// The implementation files do not exist yet; these mocks define the shape the
// tests expect at the interface boundary.
// ---------------------------------------------------------------------------

const mockGenerateJSON = vi.fn();
const mockSelectAvailableLlm = vi.fn<[], Promise<LlmProvider>>();

vi.mock("../../src/ollama/ollama-client.js", () => ({
  OllamaClient: vi.fn().mockImplementation(() => ({
    generateJSON: mockGenerateJSON,
  })),
}));

vi.mock("../../src/llm/llm-selector.js", () => ({
  LlmSelector: vi.fn().mockImplementation(() => ({
    selectAvailableLlm: mockSelectAvailableLlm,
  })),
}));

// Lazy import so env vars can be set before the module is evaluated.
async function importGate(): Promise<{
  PlanningGate: new (ollamaClient: unknown, llmSelector: unknown) => {
    plan: (
      toolName: string,
      input: Record<string, unknown>,
      intent: string,
      scope: string,
    ) => Promise<import("../../src/planning/planning-types.js").ExecutionPlan | null>;
  };
  deriveExecutor: (
    intent: string,
    scope: string,
    llm: LlmProvider,
  ) => string;
}> {
  return import("../../src/planning/planning-gate.js");
}

// ---------------------------------------------------------------------------
// Env helpers
// ---------------------------------------------------------------------------

beforeEach(() => {
  delete process.env.GEN_ENABLE_PLANNING;
  vi.clearAllMocks();
  // Default: selectAvailableLlm returns 'claude'
  mockSelectAvailableLlm.mockResolvedValue("claude" as LlmProvider);
});

afterEach(() => {
  delete process.env.GEN_ENABLE_PLANNING;
});

// ---------------------------------------------------------------------------
// TC-1: Disabled → null (no Ollama call)
// ---------------------------------------------------------------------------

describe("PlanningGate.plan — disabled gate", () => {
  it("TC-1: returns null and never calls generateJSON when GEN_ENABLE_PLANNING is not set", async () => {
    // env NOT set
    const { PlanningGate } = await importGate();
    const gate = new PlanningGate(
      { generateJSON: mockGenerateJSON },
      { selectAvailableLlm: mockSelectAvailableLlm },
    );

    const result = await gate.plan("Bash", { command: "ls" }, "code", "simple");

    expect(result).toBeNull();
    expect(mockGenerateJSON).not.toHaveBeenCalled();
  });

  it('TC-1b: returns null when GEN_ENABLE_PLANNING is "false"', async () => {
    process.env.GEN_ENABLE_PLANNING = "false";
    const { PlanningGate } = await importGate();
    const gate = new PlanningGate(
      { generateJSON: mockGenerateJSON },
      { selectAvailableLlm: mockSelectAvailableLlm },
    );

    const result = await gate.plan("Bash", { command: "ls" }, "code", "simple");

    expect(result).toBeNull();
    expect(mockGenerateJSON).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// TC-2: OllamaFails → null (no throw)
// ---------------------------------------------------------------------------

describe("PlanningGate.plan — ollama failure", () => {
  it("TC-2: returns null without rethrowing when generateJSON throws", async () => {
    process.env.GEN_ENABLE_PLANNING = "true";
    mockGenerateJSON.mockRejectedValueOnce(new Error("connection refused"));

    const { PlanningGate } = await importGate();
    const gate = new PlanningGate(
      { generateJSON: mockGenerateJSON },
      { selectAvailableLlm: mockSelectAvailableLlm },
    );

    await expect(
      gate.plan("Bash", { command: "ls" }, "code", "simple"),
    ).resolves.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// TC-3: HappyPath → ExecutionPlan returned
// ---------------------------------------------------------------------------

describe("PlanningGate.plan — happy path", () => {
  it("TC-3: returns a complete ExecutionPlan with correct executor for code+medium+claude", async () => {
    process.env.GEN_ENABLE_PLANNING = "true";
    mockGenerateJSON.mockResolvedValueOnce({
      steps: ["step 1", "step 2"],
      estimatedTokens: 800,
    });
    mockSelectAvailableLlm.mockResolvedValue("claude" as LlmProvider);

    const { PlanningGate } = await importGate();
    const gate = new PlanningGate(
      { generateJSON: mockGenerateJSON },
      { selectAvailableLlm: mockSelectAvailableLlm },
    );

    const result = await gate.plan(
      "Bash",
      { command: "npm test" },
      "code",
      "medium",
    );

    expect(result).not.toBeNull();
    expect(result!.intent).toBe("code");
    expect(result!.scope).toBe("medium");
    expect(result!.selectedLlm).toBe("claude");
    expect(result!.selectedExecutor).toBe("/codex-team");
    expect(result!.planningLatencyMs).toBeGreaterThanOrEqual(0);
  });

  // -------------------------------------------------------------------------
  // TC-4: steps passed through unmodified
  // -------------------------------------------------------------------------

  it("TC-4: passes Ollama steps through unmodified", async () => {
    process.env.GEN_ENABLE_PLANNING = "true";
    mockGenerateJSON.mockResolvedValueOnce({
      steps: ["parse args", "run tests", "report"],
      estimatedTokens: 1200,
    });

    const { PlanningGate } = await importGate();
    const gate = new PlanningGate(
      { generateJSON: mockGenerateJSON },
      { selectAvailableLlm: mockSelectAvailableLlm },
    );

    const result = await gate.plan("Bash", {}, "code", "simple");

    expect(result).not.toBeNull();
    expect(result!.steps).toHaveLength(3);
    expect(result!.steps[0]).toBe("parse args");
  });

  // -------------------------------------------------------------------------
  // TC-5: PlanIncludesSelectedLlm
  // -------------------------------------------------------------------------

  it("TC-5: selectedLlm reflects what selectAvailableLlm returns", async () => {
    process.env.GEN_ENABLE_PLANNING = "true";
    mockGenerateJSON.mockResolvedValueOnce({
      steps: ["analyze image"],
      estimatedTokens: 500,
    });
    mockSelectAvailableLlm.mockResolvedValue("gemini" as LlmProvider);

    const { PlanningGate } = await importGate();
    const gate = new PlanningGate(
      { generateJSON: mockGenerateJSON },
      { selectAvailableLlm: mockSelectAvailableLlm },
    );

    const result = await gate.plan("Bash", {}, "explore", "simple");

    expect(result).not.toBeNull();
    expect(result!.selectedLlm).toBe("gemini");
  });

  // -------------------------------------------------------------------------
  // TC-6: EstimatesTokens
  // -------------------------------------------------------------------------

  it("TC-6: populates estimatedInputTokens, estimatedOutputTokens, estimatedCostUsd", async () => {
    process.env.GEN_ENABLE_PLANNING = "true";
    mockGenerateJSON.mockResolvedValueOnce({
      steps: ["do work"],
      estimatedTokens: 2000,
    });

    const { PlanningGate } = await importGate();
    const gate = new PlanningGate(
      { generateJSON: mockGenerateJSON },
      { selectAvailableLlm: mockSelectAvailableLlm },
    );

    const result = await gate.plan("Bash", {}, "code", "simple");

    expect(result).not.toBeNull();
    expect(result!.estimatedInputTokens).toBe(2000);
    expect(result!.estimatedOutputTokens).toBeGreaterThan(0);
    expect(result!.estimatedCostUsd).toBeGreaterThanOrEqual(0);
  });

  // -------------------------------------------------------------------------
  // TC-8: OllamaReturnsEmptySteps → empty array, not null
  // -------------------------------------------------------------------------

  it("TC-8: returns non-null plan with empty steps array when Ollama returns []", async () => {
    process.env.GEN_ENABLE_PLANNING = "true";
    mockGenerateJSON.mockResolvedValueOnce({
      steps: [],
      estimatedTokens: 100,
    });

    const { PlanningGate } = await importGate();
    const gate = new PlanningGate(
      { generateJSON: mockGenerateJSON },
      { selectAvailableLlm: mockSelectAvailableLlm },
    );

    const result = await gate.plan("Bash", {}, "manage", "simple");

    expect(result).not.toBeNull();
    expect(Array.isArray(result!.steps)).toBe(true);
    expect(result!.steps).toHaveLength(0);
  });

  // -------------------------------------------------------------------------
  // TC-9: planningLatencyMs is a real wall-clock measurement
  // -------------------------------------------------------------------------

  it("TC-9: planningLatencyMs >= artificial delay of ~50ms", async () => {
    process.env.GEN_ENABLE_PLANNING = "true";
    // Introduce a 50ms delay to verify timing is real
    mockGenerateJSON.mockImplementationOnce(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                steps: ["delayed work"],
                estimatedTokens: 300,
              }),
            50,
          ),
        ),
    );

    const { PlanningGate } = await importGate();
    const gate = new PlanningGate(
      { generateJSON: mockGenerateJSON },
      { selectAvailableLlm: mockSelectAvailableLlm },
    );

    const result = await gate.plan("Bash", {}, "code", "simple");

    expect(result).not.toBeNull();
    expect(result!.planningLatencyMs).toBeGreaterThanOrEqual(50);
  }, 10_000);
});

// ---------------------------------------------------------------------------
// TC-7: deriveExecutor() routing — all branches
// ---------------------------------------------------------------------------

describe("deriveExecutor — routing rules", () => {
  it("TC-7: evaluates all routing rules in priority order", async () => {
    const { deriveExecutor } = await importGate();

    // Rule 1: code + simple + claude → /yolo
    expect(deriveExecutor("code", "simple", "claude")).toBe("/yolo");

    // Rule 2: code + medium + claude → /codex-team
    expect(deriveExecutor("code", "medium", "claude")).toBe("/codex-team");

    // Rule 3: code + complex (any llm) → spawn_agent
    expect(deriveExecutor("code", "complex", "claude")).toBe("spawn_agent");
    expect(deriveExecutor("code", "complex", "gpt")).toBe("spawn_agent");

    // Rule 4: dispatch (any scope, any llm) → spawn_agent
    expect(deriveExecutor("dispatch", "simple", "claude")).toBe("spawn_agent");
    expect(deriveExecutor("dispatch", "complex", "ollama")).toBe("spawn_agent");

    // Default: manage/explore → /yolo
    expect(deriveExecutor("manage", "simple", "claude")).toBe("/yolo");
    expect(deriveExecutor("explore", "medium", "gemini")).toBe("/yolo");
  });
});
