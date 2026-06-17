/**
 * Factory for selecting the appropriate budget manager based on BUDGET_POLICY env var.
 * Validates enum input and fails safely to normalized mode if invalid.
 */
import { BudgetPolicy, DEFAULT_TOKEN_BUDGET_CONFIG } from "./budget-types.js";
import { NormalizedBudgetManager } from "./normalized-budget-manager.js";
import { AggressiveBudgetManager } from "./aggressive-budget-manager.js";
import type { BudgetStore } from "./budget-store.js";
import type { BudgetAllocator } from "./budget-allocator.js";

export interface BudgetManager {
  checkWarningThresholds(state: unknown, config: unknown): string[];
  shouldAllowContinuation(state: unknown): boolean;
}

/**
 * Factory: returns the appropriate budget manager for the given policy.
 * Defaults to NormalizedBudgetManager if policy is invalid or unset.
 */
export function selectBudgetManager(
  store: BudgetStore,
  allocator: BudgetAllocator,
  policyEnv?: string,
): NormalizedBudgetManager | AggressiveBudgetManager {
  const policy = parseBudgetPolicy(policyEnv);
  if (policy === BudgetPolicy.AGGRESSIVE) {
    return new AggressiveBudgetManager(allocator, DEFAULT_TOKEN_BUDGET_CONFIG);
  }
  return new NormalizedBudgetManager(store, DEFAULT_TOKEN_BUDGET_CONFIG);
}

/**
 * Parse and validate BUDGET_POLICY environment variable.
 * Returns BudgetPolicy.NORMALIZED for invalid values (fail-safe).
 */
export function parseBudgetPolicy(policyEnv?: string): BudgetPolicy {
  const raw = (policyEnv ?? process.env.BUDGET_POLICY ?? "normalized").toLowerCase().trim();

  if (Object.values(BudgetPolicy).includes(raw as BudgetPolicy)) {
    return raw as BudgetPolicy;
  }

  // Invalid value — warn and default to normalized
  console.warn(`[budget-policy] Invalid BUDGET_POLICY value: "${raw}". Valid values: ${Object.values(BudgetPolicy).join(", ")}. Defaulting to "normalized".`);
  return BudgetPolicy.NORMALIZED;
}

/**
 * Returns the current active budget policy.
 * Reads from BUDGET_POLICY env var at call time (supports runtime switching).
 */
export function getActiveBudgetPolicy(): BudgetPolicy {
  return parseBudgetPolicy(process.env.BUDGET_POLICY);
}
