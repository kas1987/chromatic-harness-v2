/**
 * Type definitions for the token budget tracking system
 */
import type { LlmProvider } from "../llm/llm-types.js";

export interface AgentBudgetConfig {
  agentRole: string;
  maxTokensPerTask: number;
  maxTokensPerDay: number;
  maxExternalCallsPerTask: number;
  maxWallTimeSecondsPerTask: number;
  maxHandoffs: number;
  thresholds: {
    warnPct: number;
    hardStopPct: number;
  };
}

export interface TaskBudgetState {
  taskId: string;
  agentRole: string;
  tokensUsed: number;
  externalCalls: number;
  handoffs: number;
  wallTimeSeconds: number;
  startedAt: string; // ISO timestamp
  warnings: string[];
  stopped: boolean;
  stoppedReason?: string;
  modelUsed?: LlmProvider;
  inputTokens?: number;
  outputTokens?: number;
  estimatedCostUsd?: number;
  actualCostUsd?: number;
  budgetPolicy?: BudgetPolicy;
  fallbackModel?: LlmProvider;
}

export interface BudgetEvaluation {
  action: "allow" | "warn" | "stop";
  message?: string;
  stopReason?: string;
  utilization: {
    tokens: number; // 0-1 ratio
    calls: number;
    time: number;
  };
}

/**
 * Budget enforcement policy.
 * NORMALIZED: lenient — warnings up to 120% soft cap, then block (development mode).
 * AGGRESSIVE: strict — cost-first routing, auto-fallback, hard stops at 95% (production mode).
 */
export enum BudgetPolicy {
  NORMALIZED = "normalized",
  AGGRESSIVE = "aggressive",
}

/**
 * Token-based budget configuration for dual-policy system.
 */
export interface TokenBudgetConfig {
  maxTokensPerTask: number;
  maxTokensPerDay: number;
  dailyBudgetCapUsd: number;
  normalizedSoftCapPercent: number;  // e.g. 120 — allow up to 120% before hard stop
  aggressiveHardCapPercent: number;  // e.g. 95 — hard stop at 95% in aggressive mode
}

/**
 * Default token budget configuration.
 */
export const DEFAULT_TOKEN_BUDGET_CONFIG: TokenBudgetConfig = {
  maxTokensPerTask: 50_000,
  maxTokensPerDay: 500_000,
  dailyBudgetCapUsd: 5.0,
  normalizedSoftCapPercent: 120,
  aggressiveHardCapPercent: 95,
};
