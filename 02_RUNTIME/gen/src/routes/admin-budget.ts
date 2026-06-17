/**
 * Admin endpoints for budget management
 * Mount under /admin/budget — auth applied at mount site
 */

import { Router, Request, Response } from "express";
import { BudgetStore } from "../budget/budget-store";
import { getDefaultBudgetConfig, ROLE_CONFIGS } from "../budget/budget-config";
import { AgentBudgetConfig } from "../budget/budget-types";
import { parseBudgetPolicy } from "../budget/budget-policy-selector";
import { auditLog } from "../otel/audit-logger";

// In-memory policy store — avoids mutating process.env at runtime.
// process.env.BUDGET_POLICY is read at startup and seeded here.
let _runtimePolicy: string = process.env.BUDGET_POLICY ?? "normalized";

export const adminBudgetRouter = Router();

let budgetStore: BudgetStore | null = null;

export function initializeAdminBudgetRouter(store: BudgetStore): void {
  budgetStore = store;
}

// GET /admin/budget/configs — all default role configs (+ any overrides from DB)
adminBudgetRouter.get("/configs", (_req: Request, res: Response) => {
  const configs: Record<string, AgentBudgetConfig> = {};

  for (const role of Object.keys(ROLE_CONFIGS)) {
    if (budgetStore) {
      const overrideJson = budgetStore.getConfigOverride(role);
      if (overrideJson) {
        try {
          configs[role] = JSON.parse(overrideJson) as AgentBudgetConfig;
          continue;
        } catch {
          // Corrupt override — fall through to default
        }
      }
    }
    configs[role] = getDefaultBudgetConfig(role);
  }

  res.json(configs);
});

// GET /admin/budget/state/:taskId — current state for a specific task
adminBudgetRouter.get("/state/:taskId", (req: Request, res: Response) => {
  if (!budgetStore) {
    return res.status(503).json({ error: "Budget store not initialized" });
  }

  const state = budgetStore.getState(req.params.taskId);
  if (!state) {
    return res.status(404).json({ error: "Task not found" });
  }

  res.json(state);
});

// GET /admin/budget/states — all active (non-stopped) task states
adminBudgetRouter.get("/states", (_req: Request, res: Response) => {
  if (!budgetStore) {
    return res.status(503).json({ error: "Budget store not initialized" });
  }

  res.json(budgetStore.listActive());
});

// POST /admin/budget/configs/:role — override config for a role
adminBudgetRouter.post("/configs/:role", (req: Request, res: Response) => {
  if (!budgetStore) {
    return res.status(503).json({ error: "Budget store not initialized" });
  }

  const { role } = req.params;
  const body = req.body as Partial<AgentBudgetConfig>;

  if (!body || typeof body !== "object") {
    return res.status(400).json({ error: "Request body must be a JSON object" });
  }

  // Merge onto defaults so callers can patch individual fields
  const base = getDefaultBudgetConfig(role);
  const merged: AgentBudgetConfig = {
    ...base,
    ...body,
    agentRole: role,
    thresholds: {
      ...base.thresholds,
      ...(body.thresholds ?? {}),
    },
  };

  budgetStore.setConfigOverride(role, JSON.stringify(merged));
  res.json({ ok: true, role, config: merged });
});

/**
 * POST /admin/budget/policy
 * Switch budget enforcement policy at runtime.
 * Body: { policy: "normalized" | "aggressive" }
 */
adminBudgetRouter.post("/policy", (req: Request, res: Response) => {
  const { policy } = req.body || {};

  if (!policy || typeof policy !== "string") {
    return res.status(400).json({ error: "Body must include { policy: 'normalized' | 'aggressive' }" });
  }

  const validated = parseBudgetPolicy(policy);
  const prev = _runtimePolicy;
  _runtimePolicy = validated;

  // Audit every policy change — this is a security-relevant event
  auditLog.write({
    kind: "policy_change",
    decision: "allow",
    reason: `Budget policy changed: ${prev} → ${validated}`,
    meta: { prev, next: validated },
  });
  console.info(`[budget-policy] Policy changed: ${prev} → ${validated} at ${new Date().toISOString()}`);

  return res.json({
    currentPolicy: validated,
    previousPolicy: prev,
    updated: true,
  });
});

/** Export for use by budget-policy-selector to read the runtime value. */
export function getRuntimeBudgetPolicy(): string {
  return _runtimePolicy;
}

/**
 * GET /admin/budget/policy
 * Return current budget enforcement policy.
 */
adminBudgetRouter.get("/policy", (_req: Request, res: Response) => {
  const policy = parseBudgetPolicy(process.env.BUDGET_POLICY);
  return res.json({ currentPolicy: policy });
});
