/**
 * POST /api/delegate
 *
 * Actual multi-LLM task delegation endpoint.
 * This is what hooks.ts "suggestedLlm" was pointing toward — the router that
 * actually sends a prompt to a provider and returns the result.
 *
 * Flow:
 *   1. Select best available provider (or use caller's preference)
 *   2. Build delegation prompt (originalPrompt travels verbatim)
 *   3. Call provider.generate()
 *   4. Validate response via FallbackPolicy
 *   5. If validation fails → log failure → try next provider in fallback chain
 *   6. Return result with full audit trail
 */

import { Router, Request, Response } from "express";
import Database from "better-sqlite3";
import os from "os";
import fs from "fs";
import path from "path";
import { LlmSelector } from "../llm/llm-selector.js";
import { createClient } from "../llm/llm-client-factory.js";
import type { LlmGenerateOptions, LlmProvider, LlmTask } from "../llm/llm-types.js";
import {
  dedupeAdjacentSteps,
  filterRoutingStepsForVram,
  getRoutingSteps,
  type RoutingStep,
} from "../routing/routing-matrix.js";

// ---------------------------------------------------------------------------
// Agent role registry — loaded at startup, never mutated at runtime
// ---------------------------------------------------------------------------

interface RoleDefinition {
  description: string;
  preferredProvider?: LlmProvider;
  priority?: "high" | "normal" | "low";
  task?: Partial<LlmTask>;
  systemPromptPrefix?: string;
}

// tsx sets __dirname to "." — resolve from the source file location instead
const _rolesJsonPath = (() => {
  const candidates = [
    path.join(__dirname, "roles.json"),
    path.resolve(process.cwd(), "src/routes/roles.json"),
    path.resolve(process.cwd(), "dist/routes/roles.json"),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  throw new Error(`[delegate] roles.json not found. Tried: ${candidates.join(", ")}`);
})();

const ROLES: Record<string, RoleDefinition> = JSON.parse(
  fs.readFileSync(_rolesJsonPath, "utf-8"),
);
import { CLAUDE_MODEL_IDS } from "../llm/llm-types.js";
import { DelegationLog } from "../context/delegation-log.js";
import { FallbackPolicy } from "../context/fallback-policy.js";
import { getVramProfile, detectSessionMode } from "../context/vram-guard.js";
import { createTaskContext, buildDelegationPrompt } from "../context/task-context.js";
import type { IntentClass, ScopeLevel } from "../context/task-context.js";
import {
  ProviderCapacityTracker,
  checkOllamaReadiness,
} from "../context/provider-capacity.js";
import {
  DelegateQueue,
  QueueCapacityError,
  JobTimeoutError,
} from "../context/delegate-queue.js";
import type { JobPriority } from "../context/delegate-queue.js";
import { config } from "../config.js";

export const delegateRouter = Router();

// Fallback chain in cost order — GPT last since it's always pay-per-token
const COST_ORDERED_CHAIN: LlmProvider[] = ["claude", "gemini", "lm-studio", "ollama", "gemma", "gpt"];

function buildLegacyRoutingSteps(
  preferred: LlmProvider,
  costChain: LlmProvider[],
  ollamaLightSafe: boolean,
): RoutingStep[] {
  const providers = [preferred, ...costChain.filter((p) => p !== preferred)].filter((p) => {
    if ((p === "ollama" || p === "gemma") && !ollamaLightSafe) return false;
    return true;
  });
  return providers.map((provider) => ({ provider }));
}

function probeChainLabel(steps: RoutingStep[]): string {
  return steps
    .map((s) => (s.localModelTag ? `${s.provider}:${s.localModelTag}` : s.provider))
    .join(" → ");
}

let _selector: LlmSelector | null = null;
let _delegationLog: DelegationLog | null = null;
const _fallbackPolicy = new FallbackPolicy();
// Shared capacity tracker — tracks in-flight requests across all route calls
const _capacity = new ProviderCapacityTracker();
// Job queue — buffers bursts and dispatches as provider slots open
const _queue = new DelegateQueue(_capacity);

export function initializeDelegateRouter(db: Database.Database): void {
  _selector = new LlmSelector(createClient);
  _delegationLog = new DelegationLog(db);
}

interface DelegateRequest {
  /** The original user prompt — travels verbatim to every downstream LLM. */
  prompt: string;
  /**
   * Named agent role (from roles.json). Applies a preset of provider, task,
   * priority, and system prompt. All fields can still be overridden individually.
   * e.g. "coder", "reviewer", "architect", "tester", "analyst", "debugger"
   */
  role?: string;
  /** Optional: force a specific provider. If unavailable, falls back normally. */
  preferredProvider?: LlmProvider;
  /** Task metadata for routing decisions. */
  task?: Partial<LlmTask> & { filePaths?: string[] };
  /** Optional elevation context (Claude's domain knowledge to prepend). */
  claudeElevation?: string;
  /** Hard constraints the downstream LLM must honour. */
  constraints?: string[];
  /** Expected output format description. Used for response validation. */
  expectedOutputFormat?: string;
  /** Max tokens to request from the provider. */
  maxTokens?: number;
  /**
   * Job priority — controls queue position when all providers are busy.
   *   "high"   interactive/user-facing requests  (jump the queue)
   *   "normal" workflow/hook-driven requests      (default)
   *   "low"    batch/overnight tasks              (yield to everything else)
   */
  priority?: JobPriority;
  /**
   * Per-job timeout in ms (default 60s).
   * Includes time spent waiting in queue + actual LLM call latency.
   */
  timeoutMs?: number;
  /**
   * interactive (default): all providers exhausted => HTTP 503.
   * background: all exhausted => HTTP 200 with degraded empty result (fail-open for batch callers).
   */
  workflowType?: "interactive" | "background";
  /** Optional analytics envelope — echoed in response when set. See MODEL-DISPATCH-GATEWAY.md. */
  repo?: string;
  userId?: string;
  sessionId?: string;
  taskIntent?: string;
  riskLevel?: "low" | "medium" | "high";
  toolContext?: string;
}

interface DelegateResponse {
  result: string;
  provider: LlmProvider;
  model: string;
  traceId: string;
  fallbackTriggered: boolean;
  fallbackChain: LlmProvider[];
  latencyMs: number;
  role?: string;
  requestEcho?: {
    repo?: string;
    userId?: string;
    sessionId?: string;
    taskIntent?: string;
    riskLevel?: string;
    toolContext?: string;
    workflowType?: string;
  };
  failureMode?: "fail_closed" | "fail_open";
  degraded?: boolean;
  lastError?: string;
}

function buildRequestEcho(body: DelegateRequest): DelegateResponse["requestEcho"] {
  const { repo, userId, sessionId, taskIntent, riskLevel, toolContext, workflowType } = body;
  if (
    repo === undefined &&
    userId === undefined &&
    sessionId === undefined &&
    taskIntent === undefined &&
    riskLevel === undefined &&
    toolContext === undefined &&
    workflowType === undefined
  ) {
    return undefined;
  }
  return { repo, userId, sessionId, taskIntent, riskLevel, toolContext, workflowType };
}

delegateRouter.post("/", async (req: Request, res: Response) => {
  const body: DelegateRequest = req.body || {};
  const startTime = Date.now();

  if (!body.prompt || typeof body.prompt !== "string" || !body.prompt.trim()) {
    return res.status(400).json({ error: "prompt is required" });
  }
  if (body.prompt.length > 200_000) {
    return res.status(400).json({ error: "prompt exceeds maximum length (200,000 chars)" });
  }

  // Apply role preset — caller's explicit fields win over role defaults
  if (body.role) {
    const role = ROLES[body.role];
    if (!role) {
      return res.status(400).json({
        error: `Unknown role "${body.role}"`,
        available: Object.keys(ROLES),
      });
    }
    // Merge in order: role defaults < body overrides
    if (role.preferredProvider && !body.preferredProvider) {
      body.preferredProvider = role.preferredProvider;
    }
    if (role.priority && !body.priority) {
      body.priority = role.priority;
    }
    if (role.task) {
      body.task = { ...role.task, ...(body.task ?? {}) };
    }
    // Prepend role system prompt to any caller-supplied claudeElevation
    if (role.systemPromptPrefix) {
      body.claudeElevation = body.claudeElevation
        ? `${role.systemPromptPrefix}\n\n${body.claudeElevation}`
        : role.systemPromptPrefix;
    }
  }

  // Enqueue the job — this transparently buffers the request when all provider
  // slots are occupied and dispatches it as capacity opens up.
  try {
    const result = await _queue.enqueue<DelegateResponse>(
      () => _executeDelegation(body, startTime),
      {
        priority: body.priority ?? "normal",
        timeoutMs: body.timeoutMs,
      },
    );
    return res.json(result);
  } catch (err) {
    if (err instanceof QueueCapacityError) {
      const queueStats = _queue.getStats();
      return res.status(429).json({
        error: "Delegate queue at capacity — too many concurrent jobs",
        pending: queueStats.pending,
        inFlight: queueStats.inFlight,
        maxDepth: err.maxDepth,
        hint: "Use priority='high' for interactive requests, or back off and retry for batch jobs.",
      });
    }
    if (err instanceof JobTimeoutError) {
      return res.status(504).json({
        error: "Job timed out waiting for a provider slot",
        hint: `Increase timeoutMs (current: ${body.timeoutMs ?? 60000}ms) or reduce concurrent load.`,
      });
    }
    // Propagate provider-level errors (503 all-exhausted) that _executeDelegation throws
    const httpErr = err as { statusCode?: number; body?: unknown; message?: string };
    if (httpErr.statusCode) {
      return res.status(httpErr.statusCode).json(httpErr.body);
    }
    return res.status(500).json({ error: (err as Error).message });
  }
});

// S- prefix pattern: matches filenames like S-12345_01_1.png, S-seed_variant.jpg
// Anchored to path separator or start-of-string so it only fires on the filename component.
const NSFW_FILE_PREFIX_RE = /(?:^|[\\/])S-\d/i;
const NSFW_PATH_KEYWORD_RE = /\bnsfw\b/i;

/**
 * Auto-detect NSFW context from file paths embedded in the prompt or passed explicitly.
 * Two signals (either triggers nsfwContext=true):
 *   1. "S-" prefix on a filename (e.g., S-12345_01_1.png) — project convention
 *   2. "nsfw" anywhere in the path (e.g., /nsfw/output/, storyboard_nsfw/)
 * Returns false if no signal found — callers can still set nsfwContext explicitly.
 */
function _detectNsfwContext(prompt: string, filePaths?: string[]): boolean {
  // Check explicit file paths first (cheapest)
  if (filePaths?.length) {
    for (const fp of filePaths) {
      if (NSFW_FILE_PREFIX_RE.test(fp) || NSFW_PATH_KEYWORD_RE.test(fp)) return true;
    }
  }
  // Scan the prompt text for embedded file references
  if (NSFW_FILE_PREFIX_RE.test(prompt) || NSFW_PATH_KEYWORD_RE.test(prompt)) return true;
  return false;
}

/**
 * Core delegation logic — probe the fallback chain and return the first successful result.
 * Called by the queue dispatcher once a slot becomes available.
 * Throws a structured error (with .statusCode) on all-providers-exhausted.
 */
async function _executeDelegation(body: DelegateRequest, startTime: number): Promise<DelegateResponse> {

  // Auto-detect NSFW context from file paths in the prompt or task metadata.
  // Convention: "S-" prefix on filenames (e.g., S-12345_01_1.png) or "nsfw" anywhere in the path.
  const nsfwAutoDetected = _detectNsfwContext(body.prompt, body.task?.filePaths);

  const llmTask: LlmTask = {
    intent:                body.task?.intent ?? "other",
    scope:                 body.task?.scope ?? "medium",
    requiresCode:          body.task?.requiresCode ?? false,
    requiresVision:        body.task?.requiresVision ?? false,
    requiresLocal:         body.task?.requiresLocal ?? false,
    nsfwContext:            body.task?.nsfwContext || nsfwAutoDetected,
    budgetConstraint:      body.task?.budgetConstraint ?? "medium",
    estimatedInputTokens:  body.task?.estimatedInputTokens,
    maxOutputTokens:       body.task?.maxOutputTokens,
    claudeModelTier:       body.task?.claudeModelTier,
  };

  const intentClass = (body.task?.intent as IntentClass | undefined) ?? "other";
  const scopeLevel  = llmTask.scope as ScopeLevel;

  // Policy pipeline (Track A — see repo docs/architecture/MODEL-DISPATCH-GATEWAY.md):
  // HTTP auth + validation + queue already applied on the route. Here: task risk
  // heuristics (nsfwContext on llmTask), VRAM/routing constraints, then provider probes
  // and generate(). Single trace_id for all attempts in this job.
  const baseCtx = createTaskContext({
    originalPrompt: body.prompt,
    toolName: "delegate",
    intentClass,
    scopeLevel,
    claudeElevation: body.claudeElevation,
    constraints: body.constraints,
    selectedProvider: "claude",
    selectedModel: "routing-pending",
    delegatedTask: body.prompt,
    expectedOutputFormat: body.expectedOutputFormat,
  });

  // VRAM check: if Ollama unsafe in current session, remove it from viable chain
  const vramProfile = getVramProfile(detectSessionMode());

  const preferred = body.preferredProvider ?? (_selector ? await _selector.selectBestLlm(llmTask) : "claude");

  let probeSteps: RoutingStep[];
  if (body.preferredProvider) {
    probeSteps = buildLegacyRoutingSteps(preferred, COST_ORDERED_CHAIN, vramProfile.ollamaLightSafe);
  } else {
    const matrixSteps = getRoutingSteps(body.taskIntent);
    if (matrixSteps?.length) {
      probeSteps = dedupeAdjacentSteps(
        filterRoutingStepsForVram(matrixSteps, vramProfile.ollamaLightSafe),
      );
      if (probeSteps.length === 0) {
        probeSteps = buildLegacyRoutingSteps(preferred, COST_ORDERED_CHAIN, vramProfile.ollamaLightSafe);
      }
    } else {
      probeSteps = buildLegacyRoutingSteps(preferred, COST_ORDERED_CHAIN, vramProfile.ollamaLightSafe);
    }
  }

  const fallbackChain: LlmProvider[] = [];
  let lastError = "";
  let fallbackTriggered = false;

  for (let attempt = 1; attempt <= probeSteps.length; attempt++) {
    const step = probeSteps[attempt - 1];
    const provider = step.provider;
    const client = createClient(provider, config);

    // --- Capacity check: skip providers that are already saturated ---
    if (_capacity.isAtCapacity(provider)) {
      fallbackChain.push(provider);
      fallbackTriggered = true;
      lastError = `${provider}: at capacity (too many in-flight requests)`;
      console.warn(`[delegate] ${provider} at capacity — skipping`);
      if (_delegationLog) {
        const ctx = { ...baseCtx, selectedProvider: provider, selectedModel: provider };
        _delegationLog.record({
          traceId: baseCtx.traceId,
          attemptNumber: attempt,
          provider,
          model: provider,
          promptSent: buildDelegationPrompt(ctx),
          response: null,
          success: false,
          latencyMs: Date.now() - startTime,
          failureReason: "unavailable",
          fallbackTriggered: true,
          resolvedBy: null,
          fallbackNote: lastError,
        });
      }
      continue;
    }

    // --- Ollama model-swap check: don't route if a different model is actively running ---
    let ollamaTag = "";
    if (provider === "ollama" || provider === "gemma") {
      ollamaTag =
        provider === "gemma"
          ? step.localModelTag?.trim() || config.gemmaOllamaModel
          : step.localModelTag?.trim() || config.ollamaModel;
      const readiness = await checkOllamaReadiness(config.ollamaUrl, ollamaTag);
      if (readiness === "busy" || readiness === "swap") {
        // A different model (e.g. vision model doing image tagging) is loaded.
        // Routing here would either queue behind it or trigger an expensive model swap.
        fallbackChain.push(provider);
        fallbackTriggered = true;
        lastError = `ollama: ${readiness === "busy" ? "large/vision model active (VRAM occupied)" : "model swap needed — skipping to avoid pipeline disruption"}`;
        console.warn(`[delegate] ollama readiness=${readiness} for model=${ollamaTag} (${provider}) — skipping`);
        if (_delegationLog) {
          const ctx = { ...baseCtx, selectedProvider: provider, selectedModel: provider };
          _delegationLog.record({
            traceId: baseCtx.traceId,
            attemptNumber: attempt,
            provider,
            model: provider,
            promptSent: buildDelegationPrompt(ctx),
            response: null,
            success: false,
            latencyMs: Date.now() - startTime,
            failureReason: "unavailable",
            fallbackTriggered: true,
            resolvedBy: null,
            fallbackNote: lastError,
          });
        }
        continue;
      }
    }

    // --- Same model-swap check for LM Studio ---
    // LM Studio only loads one model at a time; if the wrong one is loaded, skip.
    // We rely on the generate() call failing fast rather than a pre-check
    // since LM Studio doesn't expose a /api/ps equivalent.

    // Gemma isAvailable() checks GEN_GEMMA_OLLAMA_MODEL only; skip when matrix supplies a different tag.
    const skipGemmaAvailCheck = provider === "gemma" && Boolean(step.localModelTag?.trim());
    const available = skipGemmaAvailCheck
      ? true
      : await client.isAvailable().catch(() => false);
    if (!available) {
      if (_delegationLog) {
        const ctx = { ...baseCtx, selectedProvider: provider, selectedModel: provider };
        _delegationLog.record({
          traceId: baseCtx.traceId,
          attemptNumber: attempt,
          provider,
          model: provider,
          promptSent: buildDelegationPrompt(ctx),
          response: null,
          success: false,
          latencyMs: Date.now() - startTime,
          failureReason: "unavailable",
          fallbackTriggered: true,
          resolvedBy: null,
          fallbackNote: `${provider} unavailable — trying next in chain`,
        });
      }
      fallbackChain.push(provider);
      fallbackTriggered = attempt > 1;
      continue;
    }

    const modelName =
      provider === "claude"
        ? CLAUDE_MODEL_IDS[(_selector?.selectClaudeTier(llmTask) ?? "haiku")]
        : provider === "ollama" || provider === "gemma"
          ? ollamaTag
          : provider;

    const taskCtx = {
      ...baseCtx,
      selectedProvider: provider,
      selectedModel: modelName,
      claudeTier: provider === "claude" ? (_selector?.selectClaudeTier(llmTask) ?? "haiku") : undefined,
      delegatedTask: body.prompt,
      expectedOutputFormat: body.expectedOutputFormat,
    };

    const delegationPrompt = buildDelegationPrompt(taskCtx);
    const callStart = Date.now();

    // Acquire a capacity slot — released in finally block regardless of outcome
    const slotAcquired = _capacity.acquire(provider);
    if (!slotAcquired) {
      // Capacity was free when we checked above but another concurrent request
      // just took the last slot. Skip this provider.
      fallbackChain.push(provider);
      fallbackTriggered = true;
      lastError = `${provider}: slot exhausted by concurrent request`;
      if (_delegationLog) {
        _delegationLog.record({
          traceId: taskCtx.traceId,
          attemptNumber: attempt,
          provider,
          model: modelName,
          promptSent: buildDelegationPrompt(taskCtx),
          response: null,
          success: false,
          latencyMs: Date.now() - startTime,
          failureReason: "unavailable",
          fallbackTriggered: true,
          resolvedBy: null,
          fallbackNote: lastError,
        });
      }
      continue;
    }

    try {
      const genOpts: LlmGenerateOptions = {
        maxTokens: body.maxTokens ?? llmTask.maxOutputTokens,
      };
      const tag = step.localModelTag?.trim();
      if (tag && (provider === "ollama" || provider === "gemma")) {
        genOpts.localModelTag = tag;
      }
      const raw = await client.generate(delegationPrompt, genOpts);

      const latencyMs = Date.now() - callStart;
      const validationFailure = _fallbackPolicy.validateResponse(raw);

      if (validationFailure) {
        // Response invalid — check if we should fall back
        const shouldFallback = _fallbackPolicy.shouldFallback(validationFailure, attempt);
        if (_delegationLog) {
          _delegationLog.record({
            traceId: taskCtx.traceId,
            attemptNumber: attempt,
            provider,
            model: modelName,
            promptSent: delegationPrompt,
            response: raw ?? null,
            success: false,
            latencyMs,
            failureReason: validationFailure,
            fallbackTriggered: shouldFallback,
            resolvedBy: null,
            fallbackNote: _fallbackPolicy.fallbackNote(validationFailure),
          });
        }
        if (shouldFallback) {
          fallbackChain.push(provider);
          fallbackTriggered = true;
          lastError = `${provider}: ${validationFailure}`;
          continue;
        }
      }

      // Success
      if (_delegationLog) {
        _delegationLog.record({
          traceId: taskCtx.traceId,
          attemptNumber: attempt,
          provider,
          model: modelName,
          promptSent: delegationPrompt,
          response: raw,
          success: true,
          latencyMs,
          failureReason: null,
          fallbackTriggered,
          resolvedBy: provider,
          fallbackNote: fallbackTriggered
            ? `Resolved by ${provider} after fallback from: ${fallbackChain.join(" → ")}`
            : null,
        });
      }

      const response: DelegateResponse = {
        result: raw,
        provider,
        model: modelName,
        traceId: taskCtx.traceId,
        fallbackTriggered,
        fallbackChain,
        latencyMs: Date.now() - startTime,
        role: body.role,
        requestEcho: buildRequestEcho(body),
      };

      _capacity.release(provider);
      return response;

    } catch (err) {
      _capacity.release(provider);
      const latencyMs = Date.now() - callStart;
      lastError = `${provider}: ${(err as Error).message}`;
      const shouldFallback = _fallbackPolicy.shouldFallback("provider_error", attempt);

      if (_delegationLog) {
        _delegationLog.record({
          traceId: taskCtx.traceId,
          attemptNumber: attempt,
          provider,
          model: modelName,
          promptSent: delegationPrompt,
          response: null,
          success: false,
          latencyMs,
          failureReason: "provider_error",
          fallbackTriggered: shouldFallback,
          resolvedBy: null,
          fallbackNote: `${provider} threw: ${(err as Error).message}`,
        });
      }

      if (shouldFallback) {
        fallbackChain.push(provider);
        fallbackTriggered = true;
        continue;
      }
    }
  }

  const wf = body.workflowType ?? "interactive";
  const lastProvider =
    probeSteps.length > 0 ? probeSteps[probeSteps.length - 1].provider : "claude";

  if (_delegationLog) {
    const ctx = { ...baseCtx, selectedProvider: lastProvider, selectedModel: lastProvider };
    _delegationLog.record({
      traceId: baseCtx.traceId,
      attemptNumber: probeSteps.length + 1,
      provider: lastProvider,
      model: lastProvider,
      promptSent: buildDelegationPrompt(ctx),
      response: null,
      success: false,
      latencyMs: Date.now() - startTime,
      failureReason: "retry_exhausted",
      fallbackTriggered: true,
      resolvedBy: null,
      fallbackNote: `All providers exhausted (workflowType=${wf}): ${lastError}`,
    });
  }

  if (wf === "background") {
    return {
      result: "",
      provider: lastProvider,
      model: String(lastProvider),
      traceId: baseCtx.traceId,
      fallbackTriggered: true,
      fallbackChain,
      latencyMs: Date.now() - startTime,
      role: body.role,
      requestEcho: buildRequestEcho(body),
      failureMode: "fail_open",
      degraded: true,
      lastError,
    };
  }

  const exhaustedErr = Object.assign(
    new Error("All LLM providers failed or unavailable"),
    {
      statusCode: 503,
      body: {
        error: "All LLM providers failed or unavailable",
        lastError,
        fallbackChain,
        traceId: baseCtx.traceId,
        hint: `Chain tried: ${probeChainLabel(probeSteps)}. Check provider availability and API keys.`,
      },
    },
  );
  throw exhaustedErr;
}

/**
 * GET /api/delegate/status
 * Returns current provider availability and fallback chain order.
 */
delegateRouter.get("/status", async (_req: Request, res: Response) => {
  const vramProfile = getVramProfile(detectSessionMode());
  const statuses: Record<string, { available: boolean; reason?: string }> = {};

  for (const provider of COST_ORDERED_CHAIN) {
    try {
      const client = createClient(provider, config);
      const available = await client.isAvailable();
      statuses[provider] = { available };
    } catch {
      statuses[provider] = { available: false, reason: "probe failed" };
    }
  }

  res.json({
    chainOrder: COST_ORDERED_CHAIN,
    providers: statuses,
    vram: {
      mode: vramProfile.mode,
      ollamaLightSafe: vramProfile.ollamaLightSafe,
      lmStudioSafe: vramProfile.lmStudioSafe,
      note: vramProfile.note,
    },
  });
});

/**
 * GET /api/delegate/queue
 * Returns current job queue depth, in-flight counts, and per-provider capacity snapshot.
 * Use this to monitor pipeline load before firing a batch of delegation requests.
 *
 * Response shape:
 *   {
 *     pending: number,           // jobs waiting for a provider slot
 *     inFlight: number,          // jobs actively executing
 *     totalAccepted: number,     // lifetime accepted jobs
 *     totalCompleted: number,
 *     totalFailed: number,
 *     totalTimedOut: number,
 *     byPriority: { high, normal, low },
 *     capacitySnapshot: {
 *       claude:    { inFlight, maxSlots, atCapacity },
 *       gemini:    { ... },
 *       lm-studio: { ... },
 *       ollama:    { ... },
 *       gpt:       { ... }
 *     }
 *   }
 */
delegateRouter.get("/queue", (_req: Request, res: Response) => {
  res.json(_queue.getStats());
});

/**
 * GET /api/delegate/roles
 * Returns the full agent role registry — names, descriptions, and routing defaults.
 * Use this to populate role selectors in the UI or validate role names before dispatch.
 */
delegateRouter.get("/roles", (_req: Request, res: Response) => {
  res.json(ROLES);
});

/**
 * GET /api/delegate/services
 * Probes all local companion services and returns their availability, latency,
 * and any relevant payload data (loaded models, queue depth, etc.).
 *
 * Runs checks via the server so the browser avoids cross-origin fetch issues
 * with services that don't set CORS headers (ComfyUI, LM Studio, etc.).
 */
delegateRouter.get("/services", async (_req: Request, res: Response) => {
  const probes: Array<{ id: string; url: string }> = [
    { id: "comfyui",       url: "http://127.0.0.1:8188/system_stats" },
    { id: "comfyui_queue", url: "http://127.0.0.1:8188/queue" },
    { id: "ollama_ps",     url: `${config.ollamaUrl}/api/ps` },
    { id: "ollama_tags",   url: `${config.ollamaUrl}/api/tags` },
    { id: "lmstudio",      url: `${config.lmStudioUrl}/models` },
    { id: "tts",           url: `${config.ttsUrl}/health` },
    { id: "vite",          url: "http://localhost:5173" },
  ];

  const results = await Promise.all(
    probes.map(async ({ id, url }) => {
      const t0 = Date.now();
      try {
        const r = await fetch(url, { signal: AbortSignal.timeout(1500) });
        const latencyMs = Date.now() - t0;
        let extra: unknown = null;
        try {
          const ct = r.headers.get("content-type") ?? "";
          if (ct.includes("json")) extra = await r.json();
        } catch { /* non-JSON response, fine */ }
        return { id, available: r.ok, latencyMs, extra };
      } catch {
        return { id, available: false, latencyMs: null, extra: null };
      }
    }),
  );

  res.json(Object.fromEntries(results.map((r) => [r.id, r])));
});

/**
 * GET /api/delegate/sysinfo
 * Returns host OS and Node.js process metrics for the system monitoring tab.
 */
delegateRouter.get("/sysinfo", (_req: Request, res: Response) => {
  const cpus = os.cpus();
  res.json({
    platform:    os.platform(),
    arch:        os.arch(),
    cpuCount:    cpus.length,
    cpuModel:    cpus[0]?.model ?? "unknown",
    loadAvg:     os.loadavg(),
    totalMem:    os.totalmem(),
    freeMem:     os.freemem(),
    osUptime:    os.uptime(),
    nodeVersion: process.version,
    nodeMem:     process.memoryUsage(),
    nodeUptime:  process.uptime(),
  });
});
