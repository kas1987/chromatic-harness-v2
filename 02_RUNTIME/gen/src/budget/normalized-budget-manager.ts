/**
 * NormalizedBudgetManager — lenient, developer-focused budget enforcement.
 *
 * Philosophy: fail gracefully with early warnings; block only at hard ceiling.
 * - At 70%: "Moderate usage; 30% remaining"
 * - At 80%: "High usage; compress reasoning"
 * - At 90%: "Critical; very few requests remaining"
 * - At 100%: "At ceiling; next request may be blocked"
 * - At 120% (soft cap): hard stop
 */
import type { TaskBudgetState, AgentBudgetConfig, TokenBudgetConfig } from "./budget-types.js";
import { DEFAULT_TOKEN_BUDGET_CONFIG } from "./budget-types.js";
import type { BudgetStore } from "./budget-store.js";
import type { LlmProvider } from "../llm/llm-types.js";

export interface Warning {
  level: "info" | "warn" | "critical" | "ceiling";
  message: string;
  utilizationPct: number;
}

export interface SessionSummary {
  tokensUsed: number;
  callsUsed: number;
  timeUsed: number;
  warnings: Warning[];
  budgetPct: number;
}

export interface FallbackSuggestion {
  model: LlmProvider;
  reason: string;
  estimatedSavingsUsd?: number;
}

export class NormalizedBudgetManager {
  constructor(
    private store: BudgetStore,
    private config: TokenBudgetConfig = DEFAULT_TOKEN_BUDGET_CONFIG,
  ) {}

  /**
   * Check current utilization against warning thresholds.
   * Returns array of warnings (empty if under 70%).
   * NEVER blocks — always returns warnings, caller decides.
   */
  checkWarningThresholds(state: TaskBudgetState, budgetConfig: AgentBudgetConfig): Warning[] {
    const warnings: Warning[] = [];
    const tokenPct = budgetConfig.maxTokensPerTask > 0
      ? (state.tokensUsed / budgetConfig.maxTokensPerTask) * 100
      : 0;

    if (tokenPct >= 100) {
      warnings.push({ level: "ceiling", message: "At ceiling; next request may be blocked", utilizationPct: tokenPct });
    } else if (tokenPct >= 90) {
      warnings.push({ level: "critical", message: "Critical; very few requests remaining", utilizationPct: tokenPct });
    } else if (tokenPct >= 80) {
      warnings.push({ level: "warn", message: "High usage; compress reasoning", utilizationPct: tokenPct });
    } else if (tokenPct >= 70) {
      warnings.push({ level: "info", message: "Moderate usage; 30% remaining", utilizationPct: tokenPct });
    }

    return warnings;
  }

  /**
   * Lenient continuation check.
   * Returns true unless hard ceiling (120% of maxTokensPerTask) exceeded.
   */
  shouldAllowContinuation(state: TaskBudgetState, budgetConfig: AgentBudgetConfig): boolean {
    const softCapLimit = budgetConfig.maxTokensPerTask * (this.config.normalizedSoftCapPercent / 100);
    return state.tokensUsed < softCapLimit;
  }

  /**
   * Suggest a cheaper fallback model with cost delta.
   */
  suggestFallbackModel(currentModel: LlmProvider): FallbackSuggestion {
    // Simple fallback chain: claude → gpt → gemini → lm-studio → ollama
    const chain: LlmProvider[] = ["claude", "gpt", "gemini", "lm-studio", "ollama", "gemma", "minimax"];
    const idx = chain.indexOf(currentModel);
    const next = idx === -1 || idx === chain.length - 1 ? "ollama" : chain[idx + 1];

    return {
      model: next,
      reason: `${currentModel} budget approaching limit. Switch to ${next} for lower cost.`,
    };
  }

  /**
   * Summarize session budget usage.
   */
  summarizeSession(sessionId: string, state: TaskBudgetState, budgetConfig: AgentBudgetConfig): SessionSummary {
    const tokenPct = budgetConfig.maxTokensPerTask > 0
      ? (state.tokensUsed / budgetConfig.maxTokensPerTask) * 100
      : 0;

    return {
      tokensUsed: state.tokensUsed,
      callsUsed: state.externalCalls,
      timeUsed: state.wallTimeSeconds,
      warnings: this.checkWarningThresholds(state, budgetConfig),
      budgetPct: tokenPct,
    };
  }
}
