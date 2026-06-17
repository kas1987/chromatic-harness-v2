/**
 * Default budget configurations per agent role
 */

import { AgentBudgetConfig } from "./budget-types";

const ROLE_CONFIGS: Record<string, AgentBudgetConfig> = {
  coder: {
    agentRole: "coder",
    maxTokensPerTask: 50000,
    maxTokensPerDay: 500000,
    maxExternalCallsPerTask: 20,
    maxWallTimeSecondsPerTask: 300,
    maxHandoffs: 5,
    thresholds: { warnPct: 0.8, hardStopPct: 1.0 },
  },
  architect: {
    agentRole: "architect",
    maxTokensPerTask: 100000,
    maxTokensPerDay: 1000000,
    maxExternalCallsPerTask: 50,
    maxWallTimeSecondsPerTask: 600,
    maxHandoffs: 10,
    thresholds: { warnPct: 0.8, hardStopPct: 1.0 },
  },
  qa: {
    agentRole: "qa",
    maxTokensPerTask: 30000,
    maxTokensPerDay: 300000,
    maxExternalCallsPerTask: 15,
    maxWallTimeSecondsPerTask: 180,
    maxHandoffs: 3,
    thresholds: { warnPct: 0.8, hardStopPct: 1.0 },
  },
  intern: {
    agentRole: "intern",
    maxTokensPerTask: 10000,
    maxTokensPerDay: 50000,
    maxExternalCallsPerTask: 5,
    maxWallTimeSecondsPerTask: 120,
    maxHandoffs: 2,
    thresholds: { warnPct: 0.7, hardStopPct: 0.9 },
  },
  system: {
    agentRole: "system",
    maxTokensPerTask: 200000,
    maxTokensPerDay: 2000000,
    maxExternalCallsPerTask: 10000,
    maxWallTimeSecondsPerTask: 3600,
    maxHandoffs: 50,
    thresholds: { warnPct: 0.9, hardStopPct: 1.0 },
  },
};

/**
 * Returns the budget config for the given role. Falls back to "system" if the
 * role is not recognized.
 */
export function getDefaultBudgetConfig(role: string): AgentBudgetConfig {
  return ROLE_CONFIGS[role] ?? ROLE_CONFIGS["system"];
}

export { ROLE_CONFIGS };
