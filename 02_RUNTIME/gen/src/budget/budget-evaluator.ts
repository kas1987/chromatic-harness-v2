/**
 * Pure evaluation function: given a config and current state, decide allow/warn/stop
 */

import { AgentBudgetConfig, TaskBudgetState, BudgetEvaluation } from "./budget-types";

export function evaluateBudget(
  cfg: AgentBudgetConfig,
  state: TaskBudgetState
): BudgetEvaluation {
  const tokenRatio = state.tokensUsed / cfg.maxTokensPerTask;
  const callRatio = state.externalCalls / cfg.maxExternalCallsPerTask;
  const timeRatio = state.wallTimeSeconds / cfg.maxWallTimeSecondsPerTask;

  const utilization = {
    tokens: tokenRatio,
    calls: callRatio,
    time: timeRatio,
  };

  const maxUtil = Math.max(tokenRatio, callRatio, timeRatio);

  if (maxUtil >= cfg.thresholds.hardStopPct) {
    const dimension = pickLeadingDimension(tokenRatio, callRatio, timeRatio);
    return {
      action: "stop",
      stopReason: `Budget limit reached: ${dimension} at ${(maxUtil * 100).toFixed(1)}% of limit`,
      utilization,
    };
  }

  if (maxUtil >= cfg.thresholds.warnPct) {
    const dimension = pickLeadingDimension(tokenRatio, callRatio, timeRatio);
    return {
      action: "warn",
      message: `At ${(maxUtil * 100).toFixed(1)}% budget (${dimension}), compress reasoning`,
      utilization,
    };
  }

  return {
    action: "allow",
    utilization,
  };
}

function pickLeadingDimension(
  tokenRatio: number,
  callRatio: number,
  timeRatio: number
): string {
  const max = Math.max(tokenRatio, callRatio, timeRatio);
  if (timeRatio === max) return "wall time";
  if (callRatio === max) return "external calls";
  return "tokens";
}
