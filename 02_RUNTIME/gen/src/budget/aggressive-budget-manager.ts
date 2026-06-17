/**
 * AggressiveBudgetManager — strict, production-grade budget enforcement.
 *
 * Philosophy: minimize spend with deterministic routing and hard limits.
 * - Task complexity classification drives model routing
 * - Cost prediction runs BEFORE execution
 * - Auto-fallback (no user prompt) when model budget exhausted
 * - Hard stop at 95% utilization (vs normalized's 120% soft cap)
 */
import type { TokenBudgetConfig } from "./budget-types.js";
import { DEFAULT_TOKEN_BUDGET_CONFIG } from "./budget-types.js";
import type { BudgetAllocator } from "./budget-allocator.js";
import type { LlmProvider } from "../llm/llm-types.js";
import { estimateCost } from "./model-cost-calculator.js";

const COMPLEX_KEYWORDS = [
  "council",
  "agent",
  "spawn",
  "discovery",
  "research",
  "crank",
  "validation",
  "multi-step",
];

const ALL_PROVIDERS: LlmProvider[] = ["claude", "gpt", "gemini", "lm-studio", "ollama", "gemma", "minimax"];

export class AggressiveBudgetManager {
  private config: TokenBudgetConfig;

  constructor(
    private allocator: BudgetAllocator,
    config?: Partial<TokenBudgetConfig>,
  ) {
    this.config = { ...DEFAULT_TOKEN_BUDGET_CONFIG, ...config };
  }

  /**
   * Classify task complexity and return preferred model with fallback chain.
   */
  selectModelForTask(taskDescription: string): {
    preferred: LlmProvider;
    fallbacks: LlmProvider[];
  } {
    const lower = taskDescription.toLowerCase();
    const isComplex = COMPLEX_KEYWORDS.some((kw) => lower.includes(kw));

    if (isComplex) {
      return { preferred: "claude", fallbacks: ["gpt", "gemini", "ollama"] };
    }
    return { preferred: "ollama", fallbacks: ["gemini", "gpt", "claude"] };
  }

  /**
   * Estimate USD cost for a model + token counts.
   * Delegates to model-cost-calculator; ollama returns 0 via capability coefficients.
   */
  estimateCost(
    model: LlmProvider,
    inputTokens: number,
    outputTokens: number,
  ): number {
    return estimateCost(null, model, inputTokens, outputTokens);
  }

  /**
   * Check whether a model has sufficient remaining budget for the estimated cost.
   * Ollama is always available (its remaining budget is Infinity and cost is 0).
   */
  isModelAvailable(model: LlmProvider, estimatedCostUsd: number): boolean {
    return this.allocator.getRemainingBudget(model) >= estimatedCostUsd;
  }

  /**
   * Walk the routing chain and return the first available model.
   * Always succeeds — ollama is free and always available as final fallback.
   */
  selectAvailableModel(
    taskDescription: string,
    preferredModel?: LlmProvider,
  ): { model: LlmProvider; estimatedCostUsd: number; reason: string } {
    const routing = this.selectModelForTask(taskDescription);
    const preferred = preferredModel ?? routing.preferred;
    const fallbacks = preferredModel
      ? routing.fallbacks.filter((m) => m !== preferredModel)
      : routing.fallbacks;

    const chain: LlmProvider[] = [preferred, ...fallbacks];
    // Ensure ollama is always last resort
    if (!chain.includes("ollama")) chain.push("ollama");

    // Default token estimate: 500 input / 200 output
    const DEFAULT_INPUT = 500;
    const DEFAULT_OUTPUT = 200;

    for (const model of chain) {
      const cost = this.estimateCost(model, DEFAULT_INPUT, DEFAULT_OUTPUT);
      if (this.isModelAvailable(model, cost)) {
        if (model === preferred) {
          return { model, estimatedCostUsd: cost, reason: `Using ${model} (preferred).` };
        }
        const preferredCost = this.estimateCost(preferred, DEFAULT_INPUT, DEFAULT_OUTPUT);
        const savings = preferredCost - cost;
        const savingsStr = savings > 0 ? ` (saves $${savings.toFixed(3)})` : "";
        const preferredLabel = preferred.charAt(0).toUpperCase() + preferred.slice(1);
        const modelLabel = model.charAt(0).toUpperCase() + model.slice(1);
        return {
          model,
          estimatedCostUsd: cost,
          reason: `${preferredLabel} exceeded monthly budget. Using ${modelLabel}${savingsStr}.`,
        };
      }
    }

    // Should never reach here — ollama is always free
    return { model: "ollama", estimatedCostUsd: 0, reason: "All models exhausted. Using Ollama." };
  }

  /**
   * Check whether today's total spend across all providers is under the daily cap.
   * Returns true if execution can continue, false if blocked.
   */
  enforceSpendLimit(): boolean {
    const totalSpent = ALL_PROVIDERS.reduce(
      (sum, model) => sum + this.allocator.getSpentUsd(model),
      0,
    );
    return totalSpent < this.config.dailyBudgetCapUsd;
  }

  /**
   * Predict whether proceeding with a given model + cost would exceed its remaining budget.
   */
  predictSpendSurplus(
    model: LlmProvider,
    estimatedCostUsd: number,
  ): {
    estimatedCost: number;
    remainingBudget: number;
    surplus: number;
    canProceed: boolean;
  } {
    const remainingBudget = this.allocator.getRemainingBudget(model);
    // Cap Infinity to a large finite number for arithmetic clarity
    const remaining = isFinite(remainingBudget) ? remainingBudget : Number.MAX_SAFE_INTEGER;
    const surplus = remaining - estimatedCostUsd;
    return {
      estimatedCost: estimatedCostUsd,
      remainingBudget,
      surplus,
      canProceed: surplus >= 0,
    };
  }
}
