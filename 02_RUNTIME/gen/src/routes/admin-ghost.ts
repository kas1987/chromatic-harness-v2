import { Router, Request, Response } from "express";
import { ghostIntake } from "../ghost/ghost-intake.js";
import { ghostPolicyEngine } from "../ghost/ghost-policy.js";
import { SystemStateSnapshot } from "../ghost/ghost-types.js";

export const adminGhostRouter = Router();

/** GET /admin/ghost/status — return engine info */
adminGhostRouter.get("/status", (_req: Request, res: Response) => {
  res.json({
    status: "operational",
    intake: ghostIntake.getCacheStats(),
    policy: { ruleCount: ghostPolicyEngine.getRuleCount(), ruleNames: ghostPolicyEngine.getRuleNames() },
  });
});

/** POST /admin/ghost/evaluate — run intake + policy on an arbitrary prompt */
adminGhostRouter.post("/evaluate", (req: Request, res: Response) => {
  const { prompt, session_id, state } = req.body as {
    prompt?: string;
    session_id?: string;
    state?: Partial<SystemStateSnapshot>;
  };

  if (!prompt || typeof prompt !== "string") {
    res.status(400).json({ error: "prompt is required" });
    return;
  }

  const traceId = `admin-eval-${Date.now()}`;
  const envelope = {
    requestId: traceId,
    rawInput: prompt,
    sessionId: session_id ?? "admin-eval",
    timestamp: new Date().toISOString(),
    source: "other" as const,
  };

  const intent = ghostIntake.process(envelope);

  const systemState: SystemStateSnapshot = {
    pretoolStopsEnforced: false,
    responseMode: "normal",
    ollamaAvailable: false,
    ...state,
  };

  const decision = ghostPolicyEngine.decidePolicyForIntent(intent, systemState, traceId);

  res.json({ traceId, intent, decision });
});
