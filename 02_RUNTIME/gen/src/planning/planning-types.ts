import { LlmProvider } from "../llm/llm-types.js";

export interface ExecutionPlan {
  intent: string;
  scope: "simple" | "medium" | "complex";
  steps: string[];
  selectedLlm: LlmProvider;
  selectedExecutor: string;
  estimatedInputTokens: number;
  estimatedOutputTokens: number;
  estimatedCostUsd: number;
  planningLatencyMs: number;
}
