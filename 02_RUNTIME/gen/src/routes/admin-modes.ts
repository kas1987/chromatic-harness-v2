/**
 * Admin endpoints for response mode and enforcement management
 * Mount under /admin/modes — auth applied at mount site
 */

import { Router, Request, Response } from "express";
import { auditLog } from "../otel/audit-logger";
import {
  loadRuntimeRoutingControls,
  persistRuntimeRoutingControls,
  type RuntimeRoutingControls,
} from "../runtime/runtime-routing-controls";

export type ResponseMode = "normal" | "ollama_gate" | "dummy";

// In-memory mode store — avoids restarting service
let _runtimeResponseMode: ResponseMode = (process.env.GEN_RESPONSE_MODE as ResponseMode) ?? "normal";

// Pretool stop enforcement (default: ON for strict safety posture)
let _pretoolStopsEnabled: boolean = process.env.GEN_ENABLE_PRETOOL_STOPS !== "false";

// Safety override: fail-open is break-glass only.
const _forceFailOpenPretoolStops: boolean = process.env.GEN_FORCE_FAIL_OPEN_PRETOOL_STOPS === "true";

// Runtime controls for delegation quality and routing posture.
let _runtimeRoutingControls: RuntimeRoutingControls = loadRuntimeRoutingControls();

export const adminModesRouter = Router();

/**
 * GET /admin/modes/current
 * Return current response mode and description
 */
adminModesRouter.get("/current", (_req: Request, res: Response) => {
  const descriptions: Record<ResponseMode, string> = {
    normal: "Standard Claude response processing",
    ollama_gate: "Ollama preprocessing pass before Claude generates",
    dummy: "Fixed template response (testing mode)",
  };

  res.json({
    currentMode: _runtimeResponseMode,
    description: descriptions[_runtimeResponseMode],
    availableModes: ["normal", "ollama_gate", "dummy"],
  });
});

/**
 * GET /admin/modes/controls
 * Return current runtime controls for routing and prompt preparation.
 */
adminModesRouter.get("/controls", (_req: Request, res: Response) => {
  res.json({
    ..._runtimeRoutingControls,
    controlsFile: "./.agents/runtime-routing-controls.json",
    description: {
      promptCleanBeforeDelegate: "Normalize and clean user prompt text before delegation",
      preferOfflineRouting: "Prefer local/offline providers when viable",
      offlineAuditEnabled: "Allow scheduled/manual offline confidence audit runs",
    },
  });
});

/**
 * POST /admin/modes/controls
 * Update one or more runtime controls.
 */
adminModesRouter.post("/controls", (req: Request, res: Response) => {
  const body = (req.body ?? {}) as Partial<RuntimeRoutingControls>;
  const keys = ["promptCleanBeforeDelegate", "preferOfflineRouting", "offlineAuditEnabled"] as const;

  const next: RuntimeRoutingControls = { ..._runtimeRoutingControls };
  let changed = false;

  for (const key of keys) {
    if (typeof body[key] === "boolean") {
      next[key] = body[key] as boolean;
      changed = true;
    }
  }

  if (!changed) {
    return res.status(400).json({
      error: "Body must include at least one boolean control",
      acceptedKeys: keys,
      current: _runtimeRoutingControls,
    });
  }

  const prev = _runtimeRoutingControls;
  _runtimeRoutingControls = next;
  persistRuntimeRoutingControls(_runtimeRoutingControls);

  auditLog.write({
    kind: "policy_change",
    decision: "allow",
    reason: "Runtime routing controls updated",
    meta: {
      control: "runtime_routing_controls",
      previous: prev,
      next,
    },
  });

  console.info(
    `[runtime-controls] Updated at ${new Date().toISOString()} | promptClean=${next.promptCleanBeforeDelegate} offlineRouting=${next.preferOfflineRouting} offlineAudit=${next.offlineAuditEnabled}`,
  );

  return res.json({
    updated: true,
    current: _runtimeRoutingControls,
    timestamp: new Date().toISOString(),
  });
});

/**
 * POST /admin/modes/switch
 * Switch response mode at runtime.
 * Body: { mode: "normal" | "ollama_gate" | "dummy" }
 */
adminModesRouter.post("/switch", (req: Request, res: Response) => {
  const { mode } = req.body || {};

  if (!mode || typeof mode !== "string") {
    return res.status(400).json({
      error: "Body must include { mode: 'normal' | 'ollama_gate' | 'dummy' }",
    });
  }

  const validModes: ResponseMode[] = ["normal", "ollama_gate", "dummy"];
  if (!validModes.includes(mode as ResponseMode)) {
    return res.status(400).json({
      error: `Invalid mode. Must be one of: ${validModes.join(", ")}`,
    });
  }

  const prev = _runtimeResponseMode;
  _runtimeResponseMode = mode as ResponseMode;

  auditLog.write({
    kind: "mode_change",
    decision: "allow",
    reason: `Response mode changed: ${prev} → ${mode}`,
    meta: { prev, next: mode },
  });
  console.info(`[response-modes] Mode changed: ${prev} → ${mode} at ${new Date().toISOString()}`);

  return res.json({
    currentMode: _runtimeResponseMode,
    previousMode: prev,
    updated: true,
    timestamp: new Date().toISOString(),
  });
});

export function getRuntimeResponseMode(): ResponseMode {
  return _runtimeResponseMode;
}

/**
 * GET /admin/modes/enforcement/pretool-stops
 * Return current pretool stop enforcement state
 */
adminModesRouter.get("/enforcement/pretool-stops", (_req: Request, res: Response) => {
  return res.json({
    enforced: _pretoolStopsEnabled,
    effectiveEnforcement: isPretoolStopsEnforced(),
    forceFailOpen: _forceFailOpenPretoolStops,
    description: _pretoolStopsEnabled
      ? "Pretool stops are ENFORCED — budget and guard stops will block execution"
      : "Pretool stops are DISABLED — all windows can chat freely (stops still audited)",
    affectedStops: ["budget_stop", "bash_guard_stop", "file_guard_stop"],
    auditTrailActive: true,
  });
});

/**
 * POST /admin/modes/enforcement/pretool-stops
 * Toggle pretool stop enforcement at runtime.
 * Body: { enforce: true | false }
 */
adminModesRouter.post("/enforcement/pretool-stops", (req: Request, res: Response) => {
  const { enforce } = req.body || {};

  if (typeof enforce !== "boolean") {
    return res.status(400).json({
      error: "Body must include { enforce: true | false }",
      current: _pretoolStopsEnabled,
    });
  }

  const prev = _pretoolStopsEnabled;
  _pretoolStopsEnabled = enforce;

  auditLog.write({
    kind: "policy_change",
    decision: "allow",
    reason: `Pretool stop enforcement changed: ${prev ? "ENFORCED" : "DISABLED"} → ${enforce ? "ENFORCED" : "DISABLED"}`,
    meta: {
      control: "pretool_stops_enforcement",
      prev,
      next: enforce,
      effectiveEnforcement: isPretoolStopsEnforced(),
      forceFailOpen: _forceFailOpenPretoolStops,
      affectedConditions: ["budget_stop", "bash_guard_stop", "file_guard_stop"],
    },
  });

  const action = enforce ? "ENABLED" : "DISABLED";
  console.info(
    `[pretool-enforcement] Stops ${action} at ${new Date().toISOString()} | forceFailOpen=${_forceFailOpenPretoolStops}`,
  );

  return res.json({
    enforced: _pretoolStopsEnabled,
    effectiveEnforcement: isPretoolStopsEnforced(),
    forceFailOpen: _forceFailOpenPretoolStops,
    previousState: prev,
    updated: true,
    timestamp: new Date().toISOString(),
  });
});

export function isPretoolStopsEnforced(): boolean {
  if (_forceFailOpenPretoolStops) {
    return false;
  }
  return _pretoolStopsEnabled;
}

export function getRuntimeRoutingControls(): RuntimeRoutingControls {
  return { ..._runtimeRoutingControls };
}

export function isOfflineAuditEnabled(): boolean {
  return _runtimeRoutingControls.offlineAuditEnabled;
}
