import { LlmProvider, LLM_CAPABILITIES } from "../llm/llm-types.js";

/**
 * Estimate USD cost for a task given estimated token counts.
 * Formula: (inputTokens/1000)*costPer1kInput + (outputTokens/1000)*costPer1kOutput
 * Ollama returns 0 because its capability coefficients are both 0.0.
 * No special-case branch for any provider — result falls out of the formula.
 */
export function estimateCost(
  _task: unknown,
  model: LlmProvider,
  estimatedInputTokens: number,
  estimatedOutputTokens: number,
): number {
  const cap = LLM_CAPABILITIES[model];
  return (estimatedInputTokens / 1000) * cap.costPer1kInputUsd +
         (estimatedOutputTokens / 1000) * cap.costPer1kOutputUsd;
}

/**
 * Compute actual USD cost from real API-reported token counts.
 * Uses the same formula as estimateCost.
 */
export function actualCost(
  inputTokens: number,
  outputTokens: number,
  model: LlmProvider,
): number {
  const cap = LLM_CAPABILITIES[model];
  return (inputTokens / 1000) * cap.costPer1kInputUsd +
         (outputTokens / 1000) * cap.costPer1kOutputUsd;
}
