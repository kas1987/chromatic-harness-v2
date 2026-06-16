import { LlmProvider } from "../llm/llm-types.js";
import { estimateCost } from "../budget/model-cost-calculator.js";
import type { ExecutionPlan } from "./planning-types.js";

interface OllamaClientLike {
  generateJSON(prompt: string, schema?: unknown): Promise<unknown>;
}

interface LlmSelectorLike {
  selectAvailableLlm(): Promise<LlmProvider>;
}

interface OllamaResponse {
  steps: string[];
  estimatedTokens: number;
}

export function deriveExecutor(
  intent: string,
  scope: string,
  llm: LlmProvider,
): string {
  if (intent === "code" && scope === "simple" && llm === "claude") return "/yolo";
  if (intent === "code" && scope === "medium" && llm === "claude") return "/codex-team";
  if (intent === "code" && scope === "complex") return "spawn_agent";
  if (intent === "dispatch") return "spawn_agent";
  return "/yolo";
}

export class PlanningGate {
  private readonly enabled: boolean;
  private readonly ollamaClient: OllamaClientLike;
  private readonly llmSelector: LlmSelectorLike;

  constructor(ollamaClient: OllamaClientLike, llmSelector: LlmSelectorLike) {
    this.enabled = process.env.GEN_ENABLE_PLANNING === "true";
    this.ollamaClient = ollamaClient;
    this.llmSelector = llmSelector;
  }

  async plan(
    toolName: string,
    toolInput: unknown,
    intent: string,
    scope: "simple" | "medium" | "complex",
  ): Promise<ExecutionPlan | null> {
    if (!this.enabled) return null;

    try {
      const selectedLlm = await this.llmSelector.selectAvailableLlm();

      const prompt = `You are a planning assistant. Given the tool "${toolName}" called with input ${JSON.stringify(toolInput)}, intent "${intent}", and scope "${scope}", produce a JSON execution plan with the shape: { "steps": string[], "estimatedTokens": number }.`;

      const t0 = Date.now();
      const raw = await this.ollamaClient.generateJSON(prompt);
      const planningLatencyMs = Date.now() - t0;

      const response = raw as OllamaResponse;
      const steps: string[] = Array.isArray(response.steps) ? response.steps : [];
      const estimatedInputTokens = typeof response.estimatedTokens === "number" ? response.estimatedTokens : 0;
      const estimatedOutputTokens = Math.round(estimatedInputTokens * 0.3);
      const estimatedCostUsd = estimateCost(null, selectedLlm, estimatedInputTokens, estimatedOutputTokens);
      const selectedExecutor = deriveExecutor(intent, scope, selectedLlm);

      const plan: ExecutionPlan = {
        intent,
        scope,
        steps,
        selectedLlm,
        selectedExecutor,
        estimatedInputTokens,
        estimatedOutputTokens,
        estimatedCostUsd,
        planningLatencyMs,
      };

      return plan;
    } catch {
      return null;
    }
  }
}
