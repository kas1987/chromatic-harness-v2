/**
 * Admin endpoints for the learning / adaptive-routing system.
 * Mounted under /admin/learning — auth applied at the mount site.
 */

import { Router, Request, Response } from "express";
import type { LearningStore } from "../learning/learning-store";

export const adminLearningRouter = Router();

let learningStore: LearningStore | null = null;

export function initializeAdminLearningRouter(store: LearningStore): void {
  learningStore = store;
}

// GET /admin/learning/patterns?agentRole=<role>
adminLearningRouter.get("/patterns", (req: Request, res: Response) => {
  if (!learningStore) {
    return res.status(503).json({ error: "Learning store not initialized" });
  }

  const agentRole =
    typeof req.query.agentRole === "string" ? req.query.agentRole : undefined;

  res.json(learningStore.getAllPatterns(agentRole));
});

// GET /admin/learning/outcomes/:agentRole/:intent — last 50 outcomes
adminLearningRouter.get(
  "/outcomes/:agentRole/:intent",
  (req: Request, res: Response) => {
    if (!learningStore) {
      return res.status(503).json({ error: "Learning store not initialized" });
    }

    const { agentRole, intent } = req.params;
    const outcomes = learningStore.getOutcomesForIntent(agentRole, intent, 50);
    res.json(outcomes);
  },
);

// POST /admin/learning/recompute
// Body (all optional): { agentRole?: string; intent?: string }
// Returns: { recomputed: number }
adminLearningRouter.post("/recompute", (req: Request, res: Response) => {
  if (!learningStore) {
    return res.status(503).json({ error: "Learning store not initialized" });
  }

  const body = (req.body ?? {}) as { agentRole?: unknown; intent?: unknown };
  const filterRole =
    typeof body.agentRole === "string" ? body.agentRole : undefined;
  const filterIntent =
    typeof body.intent === "string" ? body.intent : undefined;

  // Gather the set of (agentRole, intent) pairs to recompute
  const allPatterns = learningStore.getAllPatterns(filterRole);

  let recomputed = 0;

  for (const pattern of allPatterns) {
    if (filterIntent && pattern.intent !== filterIntent) {
      continue;
    }
    const result = learningStore.computeAndStorePattern(
      pattern.agentRole,
      pattern.intent,
    );
    if (result) {
      recomputed += 1;
    }
  }

  // If a specific intent was requested but no pattern exists yet, still try
  if (filterRole && filterIntent && allPatterns.length === 0) {
    const result = learningStore.computeAndStorePattern(filterRole, filterIntent);
    if (result) {
      recomputed += 1;
    }
  }

  res.json({ recomputed });
});
