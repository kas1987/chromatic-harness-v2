import { Router, Request, Response } from "express";
import path from "path";
import Database from "better-sqlite3";
import { BudgetGuard } from "../core/budget-guard";
import { NudgeTracker, NUDGE_MESSAGE } from "../core/nudge-tracker.js";
import { MemoryService } from "../memory/memory-service";
import { AgentId as CoreAgentId, ProjectId as CoreProjectId, UserId as CoreUserId, TaskId as CoreTaskId, TaskPurpose as CoreTaskPurpose } from "../core/ids";
import type { AgentContext as CoreAgentContext, TaskContext as CoreTaskContext } from "../core/context";
import type { AgentId, ProjectId, UserId, SessionId, TaskId } from "../memory/ids";
import { agentId, projectId, userId, sessionId, taskId } from "../memory/ids";
import { BudgetStore } from "../budget/budget-store";
import { evaluateBudget } from "../budget/budget-evaluator";
import { getDefaultBudgetConfig } from "../budget/budget-config";
import { getTracer } from "../otel/tracer";
import { GEN_ATTRS } from "../otel/attributes";
import { applyHookCorrelationAttributes } from "../otel/hook-correlation";
import {
  getHookCallsCounter,
  getHookLatencyHistogram,
  getMemoriesWrittenCounter,
  getBudgetStopsCounter,
  getRoutingReconciliationCounter,
  getUserPromptBypassCounter,
} from "../otel/meter";
import { extractIncomingContext } from "../otel/hook-request-context.js";
import type { LearningService } from "../learning/learning-service";
import type { OllamaEnricher } from "../ollama/ollama-enricher";
import { TtsClient } from "../tts/tts-client";
import { selectVoice, type VoiceContext } from "../tts/voice-router";
import { formatForSpeech } from "../tts/verbal-formatter";
import type { OllamaClient } from "../ollama/ollama-client";
import { config } from "../config";
import { LlmSelector, intentToRoutingHints, toProvider } from "../llm/llm-selector.js";
import { createClient } from "../llm/llm-client-factory.js";
import type { LlmProvider } from "../llm/llm-types.js";
import { sessionRoutingStore } from "../routing/session-routing-store.js";
import { hopDispatchPendingStore } from "../routing/hop-dispatch-pending.js";
import { RoutingDecisionLog } from "../routing/routing-decision-log.js";
import {
  initializeSkillDispatchRouter as _initSkillDispatch,
  getSkillDispatchRouter,
} from "../routing/skill-dispatch-router.js";
import type { SkillDispatchDecision } from "../routing/skill-dispatch-router.js";
import { BudgetAllocator } from "../budget/budget-allocator.js";
import { ModelPerformanceTracker } from "../learning/model-performance-tracker.js";
import { PlanningGate } from "../planning/planning-gate.js";
import { PromptNormalizer, PROMPT_NORMALIZER_VERSION } from "../prompting/prompt-normalizer.js";
import { ObservabilityLogger } from "../otel/observability.js";
import { auditLog } from "../otel/audit-logger.js";
import { getRuntimeResponseMode, getRuntimeRoutingControls, isPretoolStopsEnforced } from "./admin-modes.js";
import {
  parseE2eFromRequest,
  applyE2eSpanAttributes,
  mergeE2eIntoHookMetadata,
} from "../otel/e2e-request-context.js";

export const hooksRouter = Router();
const guard = new BudgetGuard();

let memoryService: MemoryService | null = null;
let budgetStore: BudgetStore | null = null;
let _nudgeTracker: NudgeTracker | null = null;
function getNudgeTracker(): NudgeTracker {
  if (!_nudgeTracker) {
    _nudgeTracker = new NudgeTracker({
      interval: config.nudgeInterval,
      ttlMs: config.nudgeTtlMs,
    });
  }
  return _nudgeTracker;
}
let learningService: LearningService | null = null;
let ollamaEnricher: OllamaEnricher | null = null;
let ttsClient: TtsClient | null = null;
let ollamaClientForTts: OllamaClient | null = null;

// Multi-LLM routing singletons (initialized lazily on first use)
let _llmSelector: LlmSelector | null = null;
let _planningGate: PlanningGate | null = null;
let _budgetAllocator: BudgetAllocator | null = null;
let lastSuggestedLlm: LlmProvider = "claude";
let _perfTracker: ModelPerformanceTracker | null = null;
let _routingDecisionLog: RoutingDecisionLog | null = null;

export function initializeLlmRouting(db: Database.Database, ollamaClient: OllamaClient | null): void {
  _perfTracker = new ModelPerformanceTracker(db);
  _llmSelector = new LlmSelector(createClient, _perfTracker);
  _budgetAllocator = new BudgetAllocator(db);
  if (ollamaClient) {
    const selectorWrapper = {
      selectAvailableLlm: () =>
        _llmSelector!.selectAvailableLlm({ intent: "code", scope: "medium", requiresCode: true }),
    };
    _planningGate = new PlanningGate(ollamaClient, selectorWrapper);
  } else {
    _planningGate = null;
  }
}

export function initializeRoutingDecisionLog(db: Database.Database): void {
  _routingDecisionLog = new RoutingDecisionLog(db);
}

export function initializeSkillDispatchRouter(db: Database.Database): void {
  _initSkillDispatch(db);
}

export function initializeHooksRouter(service: MemoryService): void {
  memoryService = service;
}

export function initializeBudgetStore(db: Database.Database): void {
  budgetStore = new BudgetStore(db);
}

export function initializeLearningService(service: LearningService): void {
  learningService = service;
}

export function initializeOllamaEnricher(enricher: OllamaEnricher): void {
  ollamaEnricher = enricher;
}

export function initializeTtsClient(client: TtsClient, ollamaClient?: OllamaClient): void {
  ttsClient = client;
  ollamaClientForTts = ollamaClient ?? null;
}

export function inferScope(
  toolName: string,
  toolInput: Record<string, unknown>
): "simple" | "medium" | "complex" {
  const readOnlyTools = ["Read", "Glob", "Grep"];
  if (readOnlyTools.includes(toolName)) return "simple";

  if (["Edit", "Write"].includes(toolName)) {
    const content = String(toolInput.content ?? toolInput.new_string ?? "");
    if (content.length > 2000) return "complex";
    if (content.length >= 500) return "medium";
    return "simple";
  }

  if (toolName === "Bash") return "medium";

  return "simple";
}

function buildQueryFromTool(tool: string, input: Record<string, any>): string {
  const parts = [tool];

  if (tool === "Bash") {
    const cmd = input.command as string;
    if (cmd) {
      parts.push(cmd.substring(0, 100));
    }
  } else if (["Write", "Edit", "MultiEdit"].includes(tool)) {
    const filePath = (input.file_path || input.filePath) as string;
    if (filePath) {
      parts.push(filePath);
    }
    if (input.new_string && typeof input.new_string === "string") {
      parts.push(input.new_string.substring(0, 100));
    }
  }

  return parts.filter((p) => p).join(" ");
}

function formatMemoriesAsContext(memories: string[]): string | undefined {
  if (memories.length === 0) return undefined;
  return "Relevant prior context:\n" + memories.join("\n");
}

const FALLBACK_TRACE_ID = "00000000000000000000000000000000";

/** Safe trace id for observability logs when span or spanContext is partial (e.g. test doubles). */
function traceIdFromSpan(span: { spanContext?: () => { traceId?: string } | undefined }): string {
  try {
    const ctx = typeof span.spanContext === "function" ? span.spanContext() : undefined;
    const tid = ctx?.traceId;
    return typeof tid === "string" && tid.length > 0 ? tid : FALLBACK_TRACE_ID;
  } catch {
    return FALLBACK_TRACE_ID;
  }
}

function inferVoiceContext(
  hasBudgetWarn: boolean,
  hasMemories: boolean,
  hasRoutingWarning: boolean,
): VoiceContext {
  if (hasBudgetWarn)      return "budget_warn";
  if (hasMemories)        return "memory_recall";
  if (hasRoutingWarning)  return "routing_suggestion";
  return "default";
}

/** Optional client report of which LLM actually handled the turn (top-level or input). */
function parseClientLlm(
  topLevel: unknown,
  input: Record<string, unknown>,
): LlmProvider | undefined {
  const raw =
    (typeof topLevel === "string" && topLevel.trim() && topLevel) ||
    (typeof input.activeLlm === "string" && input.activeLlm.trim() && input.activeLlm) ||
    (typeof input.lastModelUsed === "string" && input.lastModelUsed.trim() && input.lastModelUsed) ||
    undefined;
  return raw ? toProvider(String(raw).trim()) : undefined;
}

function routingReconciliation(
  suggested: LlmProvider,
  actual: LlmProvider | undefined,
): "match" | "mismatch" | "unknown" {
  if (actual === undefined) return "unknown";
  return actual === suggested ? "match" : "mismatch";
}

function pretoolRationale(source: string): string {
  switch (source) {
    case "read_only_tool":
      return "Read-only tools are routed to the local/light model when available.";
    case "session_intent":
      return "Using intent from the latest user-prompt normalization for this session.";
    case "default":
      return "No session hint; defaulting to code-capable routing.";
    case "error_fallback":
      return "LLM selection failed; fell back to Claude.";
    case "selector_unavailable":
      return "LLM selector not initialized; recommendation is a static default.";
    case "offline_preference_override":
      return "Offline-routing preference is enabled; local provider was selected when available.";
    default:
      return "Routing recommendation applied.";
  }
}

function isOfflineProvider(provider: LlmProvider): boolean {
  return provider === "ollama" || provider === "gemma" || provider === "lm-studio";
}

function cleanPromptForDelegation(prompt: string): string {
  const normalizedLines = prompt
    .replace(/\r\n/g, "\n")
    // eslint-disable-next-line no-control-regex
    .replace(new RegExp("[\\u0000-\\u0008\\u000B\\u000C\\u000E-\\u001F\\u007F]", "g"), "")
    .split("\n")
    .map((line) => line.replace(/[ \t]+$/g, ""));

  return normalizedLines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function intentToolCoherence(
  promptIntent: string | undefined,
  tool: string,
): "aligned" | "mismatch_soft" | "unknown" {
  if (!promptIntent) return "unknown";
  const light = ["explore", "status", "manage"];
  const heavy = ["Write", "Edit", "MultiEdit", "Bash"];
  if (light.includes(promptIntent) && heavy.includes(tool)) return "mismatch_soft";
  return "aligned";
}

interface PreToolUsePayload {
  tool: string;
  input: Record<string, unknown>;
  sessionId?: string;
  /** Same as input.activeLlm when clients only set top-level fields. */
  activeLlm?: string;
  metadata?: { e2eRunId?: string; e2eTags?: string[] };
}

interface PostToolUsePayload {
  tool: string;
  input: Record<string, unknown>;
  success: boolean;
  result?: unknown;
  /** Optional; may also be sent inside `input.sessionId` for clients that only extend input. */
  sessionId?: string;
  activeLlm?: string;
  /** Echo of last pretool `suggestedLlm` for learning / reconciliation. */
  suggestedLlm?: string;
  metadata?: { e2eRunId?: string; e2eTags?: string[] };
}

hooksRouter.post("/pretool", async (req: Request, res: Response) => {
  const payload: PreToolUsePayload = req.body || {};
  const startTime = Date.now();
  const parentCtx = extractIncomingContext(req);
  const span = getTracer().startSpan(
    "hook.pretool",
    {
      attributes: {
        [GEN_ATTRS.HOOK_EVENT]: "pretool",
        [GEN_ATTRS.AGENT_ROLE]: "system",
        [GEN_ATTRS.PROJECT_ID]: "default",
      },
    },
    parentCtx,
  );
  applyHookCorrelationAttributes(span, {
    sessionId: payload.sessionId,
    taskId: payload.input?.taskId as string | undefined,
    workflowId: payload.input?.workflowId as string | undefined,
    tool: payload.tool,
    agentRole: payload.input?.agentRole as string | undefined,
    projectId: payload.input?.projectId as string | undefined,
  });
  const e2eCtxPretool = parseE2eFromRequest(req, payload);
  applyE2eSpanAttributes(span, e2eCtxPretool);

  try {
    const coreCtx: CoreTaskContext = {
      agentId: "system" as CoreAgentId,
      agentRole: "system",
      projectId: "default" as CoreProjectId,
      userId: "user" as CoreUserId,
      trustLevel: 2,
      sessionId: "",
      taskId: "" as CoreTaskId,
      purpose: CoreTaskPurpose.OTHER,
    };

    // --- Token budget evaluation ---
    let budgetWarningMessage: string | undefined;
    if (budgetStore) {
      const taskIdStr = (payload.input?.taskId as string) || "default-task";
      const agentRole = (payload.input?.agentRole as string) || "system";

      const state = budgetStore.getOrCreate(taskIdStr, agentRole);
      budgetStore.updateWallTime(taskIdStr);
      budgetStore.incrementCalls(taskIdStr);

      const freshState = budgetStore.getState(taskIdStr) ?? state;
      const cfg = getDefaultBudgetConfig(freshState.agentRole);
      const evaluation = evaluateBudget(cfg, freshState);

      if (evaluation.action === "stop") {
        if (!isPretoolStopsEnforced()) {
          const advisoryReason = evaluation.stopReason ?? "Budget limit reached";
          auditLog.write({
            kind: "budget_bypass",
            decision: "allow",
            reason: `Pretool stop bypassed (enforcement disabled): ${advisoryReason}`,
            toolName: payload.tool,
            meta: {
              taskId: taskIdStr,
              agentRole,
              stopReason: advisoryReason,
              enforced: false,
            },
          });
          budgetWarningMessage = budgetWarningMessage ?? `Bypassed stop: ${advisoryReason}`;
        } else {
        budgetStore.markStopped(taskIdStr, evaluation.stopReason ?? "Budget limit reached");
        span.setAttribute(GEN_ATTRS.DECISION, "stop");
        span.setAttribute(GEN_ATTRS.STOP_REASON, evaluation.stopReason ?? "budget_limit");
        span.setAttribute(GEN_ATTRS.POLICY_LAYER, "budget");
        getBudgetStopsCounter().add(1, { [GEN_ATTRS.AGENT_ROLE]: agentRole });
        span.end();
        getHookLatencyHistogram().record(Date.now() - startTime, { [GEN_ATTRS.HOOK_EVENT]: "pretool" });
        getHookCallsCounter().add(1, { [GEN_ATTRS.DECISION]: "stop" });
        return res.json({
          continue: false,
          stopReason: evaluation.stopReason,
        });
        }
      }

      if (evaluation.action === "warn") {
        budgetWarningMessage = evaluation.message;
        budgetStore.addWarning(taskIdStr, evaluation.message ?? "Budget warning");
      }

      // --- Normalized budget manager warnings ---
      try {
        const { NormalizedBudgetManager } = await import("../budget/normalized-budget-manager.js");
        const manager = new NormalizedBudgetManager(budgetStore);
        const managerWarnings = manager.checkWarningThresholds(freshState, cfg);
        if (managerWarnings.length > 0) {
          budgetWarningMessage = budgetWarningMessage ?? managerWarnings[0].message;
          managerWarnings.forEach(w =>
            console.info(`[budget-normalized] ${w.level}: ${w.message} (${w.utilizationPct.toFixed(1)}%)`)
          );
        }
      } catch (err) {
        console.warn("[budget-normalized] Warning check failed:", err);
        // Fail open — never block on manager errors
      }
    }

    // For Bash commands, evaluate budget
    if (payload.tool === "Bash") {
      const command = (payload.input?.command as string) || "";
      const decision = guard.evaluateBashCommand(command, coreCtx);

      if (!decision.continue) {
        if (!isPretoolStopsEnforced()) {
          const advisoryReason = decision.stopReason ?? "bash_blocked";
          auditLog.write({
            kind: "path_guard_bypass",
            decision: "allow",
            reason: `Bash guard bypassed (enforcement disabled): ${advisoryReason}`,
            toolName: "Bash",
            meta: {
              command: command.slice(0, 200),
              stopReason: advisoryReason,
              enforced: false,
            },
          });
          budgetWarningMessage = budgetWarningMessage ?? `Bypassed stop: ${advisoryReason}`;
        } else {
        span.setAttribute(GEN_ATTRS.DECISION, "stop");
        span.setAttribute(GEN_ATTRS.STOP_REASON, decision.stopReason ?? "bash_blocked");
        span.setAttribute(GEN_ATTRS.POLICY_LAYER, "path_guard");
        getBudgetStopsCounter().add(1, { [GEN_ATTRS.AGENT_ROLE]: "system" });
        span.end();
        getHookLatencyHistogram().record(Date.now() - startTime, { [GEN_ATTRS.HOOK_EVENT]: "pretool" });
        getHookCallsCounter().add(1, { [GEN_ATTRS.DECISION]: "stop" });
        return res.json({
          continue: false,
          stopReason: decision.stopReason,
        });
        }
      }
    }

    // For Write/Edit, evaluate file path
    if (["Write", "Edit", "MultiEdit"].includes(payload.tool)) {
      const filePath =
        ((payload.input?.file_path as string) ||
          (payload.input?.filePath as string)) ||
        "";
      const decision = guard.evaluateFileWrite(filePath, coreCtx);

      if (!decision.continue) {
        if (!isPretoolStopsEnforced()) {
          const advisoryReason = decision.stopReason ?? "file_blocked";
          auditLog.write({
            kind: "path_guard_bypass",
            decision: "allow",
            reason: `File guard bypassed (enforcement disabled): ${advisoryReason}`,
            toolName: payload.tool,
            meta: {
              filePath,
              stopReason: advisoryReason,
              enforced: false,
            },
          });
          budgetWarningMessage = budgetWarningMessage ?? `Bypassed stop: ${advisoryReason}`;
        } else {
        span.setAttribute(GEN_ATTRS.DECISION, "stop");
        span.setAttribute(GEN_ATTRS.STOP_REASON, decision.stopReason ?? "file_blocked");
        span.setAttribute(GEN_ATTRS.POLICY_LAYER, "path_guard");
        getBudgetStopsCounter().add(1, { [GEN_ATTRS.AGENT_ROLE]: "system" });
        span.end();
        getHookLatencyHistogram().record(Date.now() - startTime, { [GEN_ATTRS.HOOK_EVENT]: "pretool" });
        getHookCallsCounter().add(1, { [GEN_ATTRS.DECISION]: "stop" });
        return res.json({
          continue: false,
          stopReason: decision.stopReason,
        });
        }
      }
    }

    // --- Skill dispatch routing ---
    let skillDispatch: SkillDispatchDecision | undefined;
    try {
      const skillRouter = getSkillDispatchRouter();
      if (payload.tool === "Skill" && skillRouter) {
        const skillId = (payload.input?.skill as string) ?? "";
        if (skillId) {
          const sessionHintForSkill = payload.sessionId
            ? sessionRoutingStore.get(payload.sessionId)
            : null;
          skillDispatch = skillRouter.resolve({
            skillId,
            skillArgs: payload.input,
            sessionId: payload.sessionId,
            intent: sessionHintForSkill?.intent,
            scope: sessionHintForSkill?.scope,
          });

          if (skillDispatch.mode === "block") {
            span.setAttribute("skill.dispatch.blocked", true);
            span.setAttribute("skill.dispatch.skill_id", skillId);
            span.end();
            getHookLatencyHistogram().record(Date.now() - startTime, { [GEN_ATTRS.HOOK_EVENT]: "pretool" });
            getHookCallsCounter().add(1, { [GEN_ATTRS.DECISION]: "stop" });
            return res.json({
              continue: false,
              stopReason: `Skill "${skillId}" is blocked by dispatch policy: ${skillDispatch.rationale}`,
            });
          }
        }
      }
    } catch (err) {
      console.warn("[skill-dispatch] Dispatch resolution failed, continuing:", err);
      // Fail open — never block tool use on dispatch errors
    }

    // Retrieve relevant memories for context injection
    let extraContext: string | undefined;
    let hasMemories = false;
    if (memoryService) {
      try {
        // Convert core context to memory context (cast string IDs using branded type constructors)
        const memCtx = {
          agentId: agentId(coreCtx.agentId as unknown as string),
          agentRole: coreCtx.agentRole,
          projectId: projectId(coreCtx.projectId as unknown as string),
          userId: userId(coreCtx.userId as unknown as string),
          trustLevel: coreCtx.trustLevel,
        };

        const query = buildQueryFromTool(payload.tool, payload.input);
        const memories = await memoryService.retrieveMemories(memCtx, query, {
          maxItems: 5,
          minScore: 0.5,
        });

        span.setAttribute(GEN_ATTRS.MEMORIES_RETURNED, memories.length);

        const memorySummaries = memories.map((mem) => {
          return `• ${mem.text.substring(0, 100)} (${mem.kind})`;
        });

        if (memories.length > 0) {
          hasMemories = true;
        }
        extraContext = formatMemoriesAsContext(memorySummaries);
      } catch (err) {
        console.warn("Failed to retrieve memories:", err);
        // Continue without memories - fail open
      }
    }

    // --- Adaptive routing recommendation ---
    let routingWarningMessage: string | undefined;
    if (learningService) {
      try {
        const agentRole = (payload.input?.agentRole as string) || "system";
        const recommendation = learningService.getRecommendation(
          agentRole,
          payload.tool,
          payload.input,
        );
        if (recommendation.warningMessage) {
          routingWarningMessage = recommendation.warningMessage;
        }
      } catch (err) {
        console.warn("Learning service recommendation failed:", err);
        // Fail open — don't block tool use
      }
    }

    // --- Multi-LLM routing (fail-open) ---
    const runtimeControls = getRuntimeRoutingControls();
    let suggestedLlm: LlmProvider = "claude";
    let pretoolRoutingSource:
      | "read_only_tool"
      | "session_intent"
      | "default"
      | "error_fallback"
      | "selector_unavailable"
      | "offline_preference_override" = "selector_unavailable";

    if (_llmSelector) {
      pretoolRoutingSource = "default";
      try {
        const scope = inferScope(payload.tool, payload.input);
        const isReadOnlyTool = ["Read", "Glob", "Grep"].includes(payload.tool);

        // Session-based routing: use stored hint from user-prompt hook
        const sessionHint = payload.sessionId
          ? sessionRoutingStore.get(payload.sessionId)
          : null;

        // Tool-based routing override: read-only tools always prefer Ollama
        if (isReadOnlyTool) {
          pretoolRoutingSource = "read_only_tool";
        } else if (sessionHint) {
          pretoolRoutingSource = "session_intent";
        } else {
          pretoolRoutingSource = "default";
        }

        const routingHints = isReadOnlyTool
          ? { requiresLocal: true, requiresCode: false }
          : sessionHint
            ? intentToRoutingHints(sessionHint.intent)
            : { requiresLocal: false, requiresCode: true }; // default: Claude

        const llmTask = {
          intent: sessionHint?.intent ?? "code",
          scope,
          ...routingHints,
          budgetConstraint: budgetWarningMessage ? ("low" as const) : ("medium" as const),
        };
        suggestedLlm = await _llmSelector.selectAvailableLlm(llmTask);

        if (runtimeControls.preferOfflineRouting && !isOfflineProvider(suggestedLlm)) {
          const offlineCandidate = await _llmSelector.selectAvailableLlm({
            ...llmTask,
            requiresLocal: true,
          });
          if (isOfflineProvider(offlineCandidate)) {
            suggestedLlm = offlineCandidate;
            pretoolRoutingSource = "offline_preference_override";
          }
        }

        // Budget exhaustion check with fallback
        if (_budgetAllocator && _budgetAllocator.isModelBudgetExhausted(suggestedLlm)) {
          suggestedLlm = _budgetAllocator.getFallbackModel(suggestedLlm);
          console.warn(`[llm-routing] Budget exhausted for primary provider, falling back to ${suggestedLlm}`);
        }
        lastSuggestedLlm = suggestedLlm;
      } catch (err) {
        console.warn("[llm-routing] LLM selection failed, defaulting to claude:", err);
        suggestedLlm = "claude";
        pretoolRoutingSource = "error_fallback";
      }
    }

    const activeLlm = parseClientLlm(payload.activeLlm, payload.input);
    const reconcile = routingReconciliation(suggestedLlm, activeLlm);
    getRoutingReconciliationCounter().add(1, { result: reconcile });
    const hintAgeBucket =
      pretoolRoutingSource === "session_intent" && payload.sessionId
        ? sessionRoutingStore.getHintAgeBucket(payload.sessionId)
        : null;

    // --- Planning gate (optional, fail-open) ---
    let executionPlan = null;
    if (_planningGate) {
      try {
        const scope = inferScope(payload.tool, payload.input);
        executionPlan = await _planningGate.plan(payload.tool, payload.input, "code", scope);
      } catch (err) {
        console.warn("[planning-gate] Plan failed, continuing without plan:", err);
      }
    }

    // --- TTS synthesis (optional, fail-open) ---
    let audioPath: string | undefined;
    if (ttsClient && (extraContext || budgetWarningMessage)) {
      try {
        const available = await ttsClient.isAvailable();
        if (available) {
          const textToSpeak = extraContext ?? budgetWarningMessage ?? "";
          const voiceCtx = inferVoiceContext(!!budgetWarningMessage, hasMemories, !!routingWarningMessage);
          const voiceId = selectVoice(voiceCtx);
          const spoken = await formatForSpeech(textToSpeak, config.ollamaModel, ollamaClientForTts);
          const result = await ttsClient.synthesize(spoken, voiceId);
          const filename = path.basename(result.audioPath);
          audioPath = `http://127.0.0.1:${config.port}/audio/${filename}`;
        }
      } catch (err) {
        console.warn("[tts] Synthesis failed, continuing text-only:", err);
        // Fail open
      }
    }

    const response: any = { continue: true };
    if (extraContext) {
      response.extraContext = extraContext;
    }
    if (audioPath) {
      response.audioPath = audioPath;
    }
    // Merge budget + routing warnings into a single message field
    const warningParts: string[] = [];
    if (budgetWarningMessage) warningParts.push(budgetWarningMessage);
    if (routingWarningMessage) warningParts.push(routingWarningMessage);
    if (warningParts.length > 0) {
      response.warningMessage = warningParts.join(" | ");
    }

    response.suggestedLlm = suggestedLlm;
    response.routingRationale = pretoolRationale(pretoolRoutingSource);
    if (executionPlan !== null) {
      response.executionPlan = executionPlan;
    }

    // Append skill dispatch decision to response
    if (skillDispatch?.matched) {
      response.skillDispatch = {
        target: skillDispatch.target,
        mode: skillDispatch.mode,
        fallback: skillDispatch.fallback,
        rationale: skillDispatch.rationale,
        capabilityTags: skillDispatch.capabilityTags,
      };
      // inject_context: prepend dispatch note into extraContext so Claude sees it before executing
      if (skillDispatch.mode === "inject_context") {
        const dispatchNote = `[Skill Dispatch] Route to "${skillDispatch.target}" for this skill invocation. ${skillDispatch.rationale}`;
        response.extraContext = response.extraContext
          ? `${dispatchNote}\n\n${response.extraContext}`
          : dispatchNote;
      }
    }

    try {
      const pretoolMeta: Record<string, unknown> = {
        tool: payload.tool,
        decision: "allow",
        input_keys: Object.keys(payload.input),
        pretool_routing_source: pretoolRoutingSource,
        suggested_llm: suggestedLlm,
        routing_reconciliation: reconcile,
        routing_rationale: response.routingRationale,
      };
      if (activeLlm) pretoolMeta.actual_llm = activeLlm;
      if (hintAgeBucket) pretoolMeta.session_hint_age_bucket = hintAgeBucket;
      mergeE2eIntoHookMetadata(pretoolMeta, e2eCtxPretool);
      const tracePayload = {
        model: suggestedLlm,
        ok: true,
        tokens: 0,
        cost: 0,
        metadata: pretoolMeta,
      };

      const taskIdVal = (payload.input?.taskId as string) || "default-task";
      
      const evt = ObservabilityLogger.createEvent(
        "pretool",
        "default-workflow",
        taskIdVal,
        traceIdFromSpan(span),
        "system",
        { prompt: "v1", policy: "v1", tools: "v1" },
        tracePayload
      );
      ObservabilityLogger.logEvent(evt);
    } catch (obsErr) {
      console.warn("[observability] Failed to log pretool event:", obsErr);
    }

    try {
      const sessionHint = payload.sessionId ? sessionRoutingStore.get(payload.sessionId) : null;
      _routingDecisionLog?.append({
        hookEvent: "pretool",
        sessionId: payload.sessionId,
        taskId: (payload.input?.taskId as string) || undefined,
        toolName: payload.tool,
        suggestedLlm,
        actualLlm: activeLlm,
        pretoolRoutingSource,
        routingReconciliation: reconcile,
        promptIntent: sessionHint?.intent,
        promptScope: sessionHint?.scope,
        sessionHintAgeBucket: hintAgeBucket ?? undefined,
        skillId: skillDispatch ? (payload.input?.skill as string) || undefined : undefined,
        skillDispatchTarget: skillDispatch?.target,
        skillDispatchMode: skillDispatch?.mode,
      });
    } catch (e) {
      console.warn("[routing-decision-log] pretool append failed:", e);
    }

    span.setAttribute(GEN_ATTRS.SUGGESTED_LLM, suggestedLlm);
    span.setAttribute(GEN_ATTRS.PRETOOL_ROUTING_SOURCE, pretoolRoutingSource);
    if (activeLlm) span.setAttribute(GEN_ATTRS.ACTUAL_LLM, activeLlm);
    span.setAttribute(GEN_ATTRS.ROUTING_RECONCILIATION, reconcile);
    span.setAttribute(GEN_ATTRS.SESSION_ROUTING_HIT, pretoolRoutingSource === "session_intent");
    if (hintAgeBucket) span.setAttribute(GEN_ATTRS.SESSION_HINT_AGE_BUCKET, hintAgeBucket);
    span.setAttribute(GEN_ATTRS.POLICY_LAYER, "allow");
    span.setAttribute(GEN_ATTRS.DECISION, "allow");
    span.end();
    getHookLatencyHistogram().record(Date.now() - startTime, { [GEN_ATTRS.HOOK_EVENT]: "pretool" });
    getHookCallsCounter().add(1, { [GEN_ATTRS.DECISION]: "allow" });

    res.json(response);
  } catch (err) {
    span.recordException(err as Error);
    span.setAttribute(GEN_ATTRS.DECISION, "error");
    span.end();
    getHookLatencyHistogram().record(Date.now() - startTime, { [GEN_ATTRS.HOOK_EVENT]: "pretool" });
    getHookCallsCounter().add(1, { [GEN_ATTRS.HOOK_EVENT]: "pretool", [GEN_ATTRS.DECISION]: "error" });
    console.error("Error in /hooks/pretool:", err);
    res.status(500).json({
      error: "Internal server error",
      continue: true, // Fail open - don't block Claude if Gen crashes
    });
  }
});

// Helper function for cosine similarity (used inline in pretool endpoint)
function cosineSimilarity(a: Float32Array, b: Float32Array): number {
  if (a.length !== b.length) return 0;
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  const denominator = Math.sqrt(normA) * Math.sqrt(normB);
  return denominator === 0 ? 0 : dotProduct / denominator;
}

hooksRouter.post("/posttool", async (req: Request, res: Response) => {
  const payload: PostToolUsePayload = req.body || {};
  const startTime = Date.now();
  const parentCtx = extractIncomingContext(req);
  const span = getTracer().startSpan(
    "hook.posttool",
    {
      attributes: {
        [GEN_ATTRS.HOOK_EVENT]: "posttool",
        [GEN_ATTRS.AGENT_ROLE]: "system",
        [GEN_ATTRS.PROJECT_ID]: "default",
      },
    },
    parentCtx,
  );
  const sessionFromPayload =
    payload.sessionId ?? (typeof payload.input?.sessionId === "string" ? payload.input.sessionId : undefined);
  applyHookCorrelationAttributes(span, {
    sessionId: sessionFromPayload,
    taskId: payload.input?.taskId as string | undefined,
    workflowId: payload.input?.workflowId as string | undefined,
    tool: payload.tool,
    agentRole: payload.input?.agentRole as string | undefined,
    projectId: payload.input?.projectId as string | undefined,
  });
  const e2eCtxPosttool = parseE2eFromRequest(req, payload);
  applyE2eSpanAttributes(span, e2eCtxPosttool);
  span.setAttribute(GEN_ATTRS.TOOL_SUCCESS, payload.success !== false);

  const sessionHintPost = sessionFromPayload
    ? sessionRoutingStore.get(sessionFromPayload)
    : null;
  const activeLlmPost = parseClientLlm(payload.activeLlm, payload.input);
  const suggestedEcho =
    (typeof payload.suggestedLlm === "string" && payload.suggestedLlm.trim() && payload.suggestedLlm) ||
    (typeof payload.input?.suggestedLlm === "string" && payload.input.suggestedLlm.trim() && payload.input.suggestedLlm) ||
    undefined;
  const coherence = intentToolCoherence(sessionHintPost?.intent, payload.tool);
  span.setAttribute(GEN_ATTRS.INTENT_TOOL_COHERENCE, coherence);
  if (activeLlmPost) span.setAttribute(GEN_ATTRS.ACTUAL_LLM, activeLlmPost);
  if (suggestedEcho) span.setAttribute(GEN_ATTRS.SUGGESTED_LLM, toProvider(String(suggestedEcho).trim()));

  let outcome!: "stored" | "skipped" | "error" | "memory_store_failed";

  try {
    // --- Learning: record outcome for every tool use ---
    if (learningService && payload.tool) {
      try {
        const taskIdStr = (payload.input?.taskId as string) || "default-task";
        const agentRole = (payload.input?.agentRole as string) || "system";
        const projectIdStr = (payload.input?.projectId as string) || "default";
        const durationMs = typeof payload.input?.durationMs === "number"
          ? payload.input.durationMs
          : 0;
        const tokensUsed = typeof payload.input?.tokensUsed === "number"
          ? payload.input.tokensUsed
          : 0;
        const errorMsg = payload.result && typeof (payload.result as any).error === "string"
          ? (payload.result as any).error
          : undefined;

        await learningService.recordToolOutcome({
          taskId: taskIdStr,
          agentRole,
          projectId: projectIdStr,
          toolName: payload.tool,
          input: payload.input,
          succeeded: payload.success !== false && !errorMsg,
          durationMs,
          tokensUsed,
          errorMessage: errorMsg,
          promptIntent: sessionHintPost?.intent,
          promptScope: sessionHintPost?.scope,
          activeLlm: activeLlmPost,
          suggestedLlm: suggestedEcho ? toProvider(String(suggestedEcho).trim()) : undefined,
        });
      } catch (err) {
        console.warn("Learning service recordToolOutcome failed:", err);
        // Fail open — don't block response
      }
    }

    if (_perfTracker && activeLlmPost) {
      try {
        const perfIntent = sessionHintPost?.intent ?? "code";
        const perfScope = sessionHintPost?.scope ?? inferScope(payload.tool, payload.input);
        const dur =
          typeof payload.input?.durationMs === "number" ? payload.input.durationMs : 0;
        _perfTracker.record(
          activeLlmPost,
          perfIntent,
          perfScope,
          payload.success !== false ? "success" : "failure",
          dur,
          0,
        );
      } catch (e) {
        console.warn("[model-performance] record failed:", e);
      }
    }

    // --- Token counting (budget enforcement) ---
    if (budgetStore) {
      try {
        const taskIdStr = (payload.input?.taskId as string) || "default-task";
        const tokenCount = typeof (payload.result as any)?.tokens === "number"
          ? (payload.result as any).tokens
          : typeof (payload.result as any)?.token_count === "number"
            ? (payload.result as any).token_count
            : null;

        if (tokenCount !== null) {
          budgetStore.incrementTokens(taskIdStr, tokenCount);
          console.debug(`[budget] Token count recorded: taskId=${taskIdStr} tokens=+${tokenCount}`);
        }
      } catch (error) {
        console.error("[budget] Failed to record token count:", error);
        // Fail-open: audit gap logged but continue
      }
    }

    // --- Async Ollama enrichment (fire-and-forget, non-blocking) ---
    if (ollamaEnricher) {
      ollamaEnricher
        .enrichEvent(payload.tool, payload.input, payload.success !== false)
        .then((tags) => {
          if (tags) {
            console.debug(`[ollama-enricher] ${payload.tool}: ${tags.intent}/${tags.category} risk=${tags.risk_level}`);
          }
        })
        .catch(() => {
          // Enrichment is optional — never block the response
        });
    }

    if (payload.success && ["Bash", "Write", "Edit", "MultiEdit"].includes(payload.tool)) {
      if (memoryService) {
        try {
          const memCtx = {
            agentId: agentId("system"),
            agentRole: "system",
            projectId: projectId("default"),
            userId: userId("user"),
            trustLevel: 2 as const,
            sessionId: sessionId("default-session"),
            purpose: "other" as const,
          };

          let memoryText = "";
          let memoryKind = "summary";

          if (payload.tool === "Bash") {
            const cmd = (payload.input?.command as string) || "bash command";
            memoryText = `Bash executed: ${cmd.substring(0, 80)}`;
          } else if (["Write", "Edit", "MultiEdit"].includes(payload.tool)) {
            const filePath = (payload.input?.file_path || payload.input?.filePath) as string;
            memoryText = `${payload.tool}: ${filePath || "unknown file"}`;
            if (
              filePath &&
              (filePath.includes("config") ||
                filePath.includes("schema") ||
                filePath.includes("types"))
            ) {
              memoryKind = "decision";
            }
          }

          await memoryService.createMemory(memCtx, {
            text: memoryText,
            kind: memoryKind,
            sourceStepId: null,
            sensitivity: "internal",
          });

          getMemoriesWrittenCounter().add(1, {
            [GEN_ATTRS.MEMORY_SCOPE]: "project",
            [GEN_ATTRS.MEMORY_SENSITIVITY]: "internal",
          });

          outcome = "stored";
          res.json({ status: "stored" });
        } catch (err) {
          console.warn("Failed to store memory:", err);
          outcome = "memory_store_failed";
          res.json({ status: "skipped", reason: "memory_store_failed" });
        }
      } else {
        outcome = "stored";
        res.json({ status: "stored" });
      }
    } else {
      outcome = "skipped";
      res.json({ status: "skipped", reason: "tool_failed" });
    }
  } catch (err) {
    span.recordException(err as Error);
    outcome = "error";
    console.error("Error in /hooks/posttool:", err);
    res.status(500).json({
      error: "Internal server error",
      status: "error",
    });
  } finally {
    try {
      const posttoolMeta: Record<string, unknown> = {
        tool: payload.tool,
        outcome: outcome,
        intent_tool_coherence: coherence,
      };
      if (activeLlmPost) posttoolMeta.active_llm = activeLlmPost;
      if (suggestedEcho) posttoolMeta.suggested_llm_echo = toProvider(String(suggestedEcho).trim());
      mergeE2eIntoHookMetadata(posttoolMeta, e2eCtxPosttool);
      const tracePayload = {
        model: activeLlmPost ?? "claude",
        ok: payload.success !== false && outcome !== "error",
        tokens: typeof (payload.result as any)?.tokens === "number" ? (payload.result as any).tokens : 0,
        cost: 0,
        metadata: posttoolMeta,
      };

      const taskIdVal = (payload.input?.taskId as string) || "default-task";
      
      const evt = ObservabilityLogger.createEvent(
        "posttool",
        "default-workflow",
        taskIdVal,
        traceIdFromSpan(span),
        "system",
        { prompt: "v1", policy: "v1", tools: "v1" },
        tracePayload
      );
      ObservabilityLogger.logEvent(evt);
    } catch (obsErr) {
      console.warn("[observability] Failed to log posttool event:", obsErr);
    }
    try {
      const echoProv = suggestedEcho ? toProvider(String(suggestedEcho).trim()) : undefined;
      const postReconcile = echoProv
        ? routingReconciliation(echoProv, activeLlmPost)
        : "unknown";
      _routingDecisionLog?.append({
        hookEvent: "posttool",
        sessionId: sessionFromPayload,
        taskId: (payload.input?.taskId as string) || undefined,
        toolName: payload.tool,
        suggestedLlm: echoProv,
        actualLlm: activeLlmPost,
        routingReconciliation: postReconcile,
        promptIntent: sessionHintPost?.intent,
        promptScope: sessionHintPost?.scope,
        intentToolCoherence: coherence,
      });
    } catch (e) {
      console.warn("[routing-decision-log] posttool append failed:", e);
    }
    span.setAttribute(GEN_ATTRS.DECISION, outcome);
    span.setAttribute(GEN_ATTRS.POLICY_LAYER, "post_dispatch");
    span.end();
    getHookLatencyHistogram().record(Date.now() - startTime, {
      [GEN_ATTRS.HOOK_EVENT]: "posttool",
    });
    getHookCallsCounter().add(1, {
      [GEN_ATTRS.HOOK_EVENT]: "posttool",
      [GEN_ATTRS.DECISION]: outcome,
    });
  }
});

hooksRouter.get("/llm-hint", (_req: Request, res: Response) => {
  res.json({ suggestedLlm: lastSuggestedLlm });
});

/**
 * POST /hooks/dispatch-outcome
 * Workers report async dispatch completion; lines are prepended as [DISPATCH UPDATES] on the next user-prompt for that sessionId.
 */
hooksRouter.post("/dispatch-outcome", (req: Request, res: Response) => {
  const body = req.body as {
    sessionId?: unknown;
    hop_id?: unknown;
    status?: unknown;
    summary?: unknown;
    outcome_nonce?: unknown;
  };
  const sessionId = typeof body.sessionId === "string" ? body.sessionId.trim() : "";
  const hopId = typeof body.hop_id === "string" ? body.hop_id.trim() : "";
  const outcomeNonce = typeof body.outcome_nonce === "string" ? body.outcome_nonce.trim() : "";
  if (!sessionId) {
    return res.status(400).json({ error: "sessionId is required" });
  }
  if (!hopId) {
    return res.status(400).json({ error: "hop_id is required" });
  }
  if (!outcomeNonce) {
    return res.status(400).json({ error: "outcome_nonce is required" });
  }

  const valid = hopDispatchPendingStore.consumeOutcomeToken(sessionId, hopId, outcomeNonce);
  if (!valid) {
    auditLog.write({
      kind: "policy_change",
      decision: "deny",
      reason: "Invalid or expired dispatch outcome nonce",
      sessionId,
      meta: { control: "dispatch_outcome_nonce", hopId },
    });
    return res.status(403).json({ error: "invalid_or_expired_outcome_nonce" });
  }

  const status = typeof body.status === "string" ? body.status.trim().slice(0, 128) : "completed";
  const summary = typeof body.summary === "string" ? body.summary : "";
  const line = hopDispatchPendingStore.formatUntrustedStatusLine(hopId, status, summary);
  hopDispatchPendingStore.enqueue(sessionId, line);
  return res.json({ ok: true });
});

/**
 * POST /hooks/user-prompt
 * Structures user prompts into the 8-layer Anthropic format.
 * Disable with env var: GEN_DISABLE_PROMPT_NORMALIZER=true
 * Fail-open: on any error, returns empty body (no transformation).
 */
interface UserPromptPayload {
  prompt: string;
  sessionId?: string;
  projectPath?: string;
  metadata?: { e2eRunId?: string; e2eTags?: string[] };
}

hooksRouter.post("/user-prompt", async (req: Request, res: Response) => {
  // Allow disabling the entire feature via env var to save tokens
  if (process.env.GEN_DISABLE_PROMPT_NORMALIZER === "true") {
    return res.json({});
  }

  const payload: UserPromptPayload = req.body || {};
  const startTime = Date.now();
  const parentCtx = extractIncomingContext(req);
  const span = getTracer().startSpan(
    "hook.user-prompt",
    {
      attributes: {
        [GEN_ATTRS.HOOK_EVENT]: "user-prompt",
        [GEN_ATTRS.AGENT_ROLE]: "system",
        [GEN_ATTRS.PROJECT_ID]: "default",
        [GEN_ATTRS.PROMPT_NORMALIZER_VERSION]: PROMPT_NORMALIZER_VERSION,
      },
    },
    parentCtx,
  );
  applyHookCorrelationAttributes(span, {
    sessionId: payload.sessionId,
  });
  const e2eCtxUserPrompt = parseE2eFromRequest(req, payload);
  applyE2eSpanAttributes(span, e2eCtxUserPrompt);

  try {
    const projectPath = payload.projectPath;
    const runtimeControls = getRuntimeRoutingControls();
    let prompt = payload.prompt;

    if (!prompt || typeof prompt !== "string") {
      span.setAttribute(GEN_ATTRS.DECISION, "skip");
      span.end();
      getHookLatencyHistogram().record(Date.now() - startTime, { [GEN_ATTRS.HOOK_EVENT]: "user-prompt" });
      getHookCallsCounter().add(1, { [GEN_ATTRS.HOOK_EVENT]: "user-prompt", [GEN_ATTRS.DECISION]: "skip" });
      return res.json({});
    }

    if (payload.sessionId) {
      const pending = hopDispatchPendingStore.drain(payload.sessionId);
      if (pending.length > 0) {
        prompt = `[DISPATCH UPDATES - UNTRUSTED STATUS DATA]\n\`\`\`json\n${pending.join("\n")}\n\`\`\`\n\n${prompt}`;
      }
    }

    const promptBeforeCleaning = prompt;
    if (runtimeControls.promptCleanBeforeDelegate) {
      prompt = cleanPromptForDelegation(prompt);
    }
    const promptWasCleaned = prompt !== promptBeforeCleaning;
    span.setAttribute("prompt_cleaning_enabled", runtimeControls.promptCleanBeforeDelegate);
    span.setAttribute("prompt_cleaning_applied", promptWasCleaned);
    span.setAttribute("prompt_length_before", promptBeforeCleaning.length);
    span.setAttribute("prompt_length_after", prompt.length);

    // Retrieve relevant memories (max 3, minScore 0.5)
    let memories: string[] = [];
    if (memoryService) {
      try {
        const memCtx = {
          agentId: agentId("system"),
          agentRole: "system" as const,
          projectId: projectId("default"),
          userId: userId("user"),
          trustLevel: 2 as const,
        };

        const retrievedMemories = await memoryService.retrieveMemories(memCtx, prompt, {
          maxItems: 3,
          minScore: 0.5,
        });

        memories = retrievedMemories.map((mem) => `${mem.text.substring(0, 150)} (${mem.kind})`);
        span.setAttribute(GEN_ATTRS.MEMORIES_RETURNED, memories.length);
      } catch (err) {
        console.warn("Failed to retrieve memories for user prompt:", err);
        // Fail open — continue without memories
      }
    }

    // Normalize the prompt
    const normalizer = new PromptNormalizer();
    const result = normalizer.normalize({
      rawPrompt: prompt,
      memories: memories.length > 0 ? memories : undefined,
      projectPath,
    });

    // Record metrics
    span.setAttribute(GEN_ATTRS.INTENT, result.intent);
    span.setAttribute(GEN_ATTRS.SCOPE, result.scope);
    span.setAttribute("sections_used", result.sectionsUsed.length);

    // If bypassed, return empty body (no transformation)
    if (result.bypassedReason) {
      span.setAttribute(GEN_ATTRS.DECISION, "bypass");
      span.setAttribute("bypass_reason", result.bypassedReason);
      span.end();
      getUserPromptBypassCounter().add(1, { reason: "normalizer_bypass" });
      getHookLatencyHistogram().record(Date.now() - startTime, { [GEN_ATTRS.HOOK_EVENT]: "user-prompt" });
      getHookCallsCounter().add(1, {
        [GEN_ATTRS.HOOK_EVENT]: "user-prompt",
        [GEN_ATTRS.INTENT]: result.intent,
        [GEN_ATTRS.SCOPE]: result.scope,
        [GEN_ATTRS.DECISION]: "bypass",
      });
      return res.json({});
    }

    // --- Intent-based LLM routing for this session ---
    let suggestedLlmForPrompt: LlmProvider = "claude";
    if (_llmSelector) {
      try {
        const routingHints = intentToRoutingHints(result.intent);
        const llmTask = {
          intent: result.intent,
          scope: result.scope,
          ...routingHints,
        };
        suggestedLlmForPrompt = await _llmSelector.selectAvailableLlm(llmTask);

        if (runtimeControls.preferOfflineRouting && !isOfflineProvider(suggestedLlmForPrompt)) {
          const offlineCandidate = await _llmSelector.selectAvailableLlm({
            ...llmTask,
            requiresLocal: true,
          });
          if (isOfflineProvider(offlineCandidate)) {
            suggestedLlmForPrompt = offlineCandidate;
          }
        }
      } catch (err) {
        console.warn("[llm-routing] user-prompt LLM selection failed, defaulting to claude:", err);
        suggestedLlmForPrompt = "claude";
      }
    }

    // Store routing hint for subsequent pretool calls in this session
    if (payload.sessionId) {
      sessionRoutingStore.set(payload.sessionId, suggestedLlmForPrompt, result.intent, result.scope);
    }

    try {
      const userPromptMeta: Record<string, unknown> = {
        intent: result.intent,
        scope: result.scope,
        action: "prompt_normalization",
        suggested_llm: suggestedLlmForPrompt,
        prompt_cleaning_enabled: runtimeControls.promptCleanBeforeDelegate,
        prompt_cleaning_applied: promptWasCleaned,
        prompt_length_before: promptBeforeCleaning.length,
        prompt_length_after: prompt.length,
      };
      mergeE2eIntoHookMetadata(userPromptMeta, e2eCtxUserPrompt);
      const tracePayload = {
        model: suggestedLlmForPrompt,
        ok: true,
        tokens: 0,
        cost: 0,
        metadata: userPromptMeta,
      };
      
      const evt = ObservabilityLogger.createEvent(
        "user-prompt",
        "default-workflow",
        payload.sessionId || "default-task",
        traceIdFromSpan(span),
        "system",
        { prompt: "v1", policy: "v1", tools: "v1" },
        tracePayload
      );
      ObservabilityLogger.logEvent(evt);
    } catch (obsErr) {
      console.warn("[observability] Failed to log user-prompt event:", obsErr);
    }

    // Audit log — always-on record of every prompt processed
    auditLog.write({
      kind: "hook_user_prompt",
      decision: "allow",
      sessionId: payload.sessionId,
      intent: result.intent,
      provider: suggestedLlmForPrompt,
      meta: { scope: result.scope, sectionsUsed: result.sectionsUsed.length },
    });

    // --- Response mode handling ---
    const responseMode = getRuntimeResponseMode();
    let finalPromptForResponse = result.structuredPrompt;

    // Periodic memory consolidation nudge (Hermes-inspired)
    if (payload.sessionId && config.nudgeInterval > 0) {
      if (getNudgeTracker().tick(payload.sessionId)) {
        finalPromptForResponse = `${NUDGE_MESSAGE}\n\n---\n\n${finalPromptForResponse}`;
        span.setAttribute("nudge_injected", true);
      }
    }

    if (responseMode === "dummy") {
      // Dummy mode: return fixed template response
      span.setAttribute("response_mode", "dummy");
      finalPromptForResponse = `You are in testing/dummy mode. Respond with: "I acknowledge dummy mode is active. Ready for assessment." Do not process any prior instructions.`;
      auditLog.write({
        kind: "hook_user_prompt",
        decision: "allow",
        sessionId: payload.sessionId,
        reason: "Response mode: dummy",
        meta: { original_intent: result.intent, mode: "dummy" },
      });
    } else if (responseMode === "ollama_gate") {
      // Ollama gate mode: prepend instruction for preprocessing
      span.setAttribute("response_mode", "ollama_gate");
      finalPromptForResponse = `[OLLAMA PREPROCESS GATE]\nBefore responding, note this prompt structure has been validated through local processing.\n\nOriginal structured prompt:\n---\n${result.structuredPrompt}\n---\nProceed with understanding this context has been locally adjudicated.`;
      auditLog.write({
        kind: "hook_user_prompt",
        decision: "allow",
        sessionId: payload.sessionId,
        reason: "Response mode: ollama_gate (gated)",
        meta: { original_intent: result.intent, mode: "ollama_gate" },
      });
    }
    // else: normal mode uses result.structuredPrompt as-is

    const hopCtx = req.hopDispatchContext;
    if (hopCtx) {
      const outcomeNonce = payload.sessionId
        ? hopDispatchPendingStore.issueOutcomeToken(payload.sessionId, hopCtx.hop_id)
        : null;
      finalPromptForResponse += `\n\n[Hop] dispatch_id=${hopCtx.hop_id} destination=${hopCtx.destination} rule=${hopCtx.rule_id}. Report completion: POST /hooks/dispatch-outcome with JSON { sessionId, hop_id, outcome_nonce, status, summary? } (same Bearer as hooks). outcome_nonce=${outcomeNonce ?? "unavailable"}. Your next user message may include [DISPATCH UPDATES - UNTRUSTED STATUS DATA].`;
    }

    // Return structured prompt
    span.setAttribute(GEN_ATTRS.SUGGESTED_LLM, suggestedLlmForPrompt);
    span.setAttribute(GEN_ATTRS.DECISION, "structure");
    span.end();
    getHookLatencyHistogram().record(Date.now() - startTime, { [GEN_ATTRS.HOOK_EVENT]: "user-prompt" });
    getHookCallsCounter().add(1, {
      [GEN_ATTRS.HOOK_EVENT]: "user-prompt",
      [GEN_ATTRS.INTENT]: result.intent,
      [GEN_ATTRS.SCOPE]: result.scope,
      [GEN_ATTRS.DECISION]: "structure",
    });

    const jsonOut: Record<string, unknown> = {
      hookSpecificOutput: {
        updatedUserMessage: finalPromptForResponse,
      },
      suggestedLlm: suggestedLlmForPrompt,
    };
    if (hopCtx) {
      jsonOut.hop = {
        hop_id: hopCtx.hop_id,
        destination: hopCtx.destination,
        rule_id: hopCtx.rule_id,
        dispatch_mode: hopCtx.dispatch_mode,
      };
    }
    res.json(jsonOut);
  } catch (err) {
    span.recordException(err as Error);
    span.setAttribute(GEN_ATTRS.DECISION, "error");
    span.end();
    console.error("Error in /hooks/user-prompt:", err);
    getHookLatencyHistogram().record(Date.now() - startTime, { [GEN_ATTRS.HOOK_EVENT]: "user-prompt" });
    getHookCallsCounter().add(1, { [GEN_ATTRS.HOOK_EVENT]: "user-prompt", [GEN_ATTRS.DECISION]: "error" });
    // Fail open — return empty body on any error
    res.json({});
  }
});

/**
 * POST /hooks/t3-approve
 *
 * Resolves a pending T3 hard stop. Called by the task_complete_gate.py
 * Python hook client after the user responds with /approve, /approve-conditions,
 * or /reject. Updates t3_approvals.status and emits a structured audit event.
 *
 * Body: {
 *   approvalId: string,          // UUID from the pending t3_approvals row
 *   sessionId: string,
 *   decision: "approve" | "approve_with_conditions" | "reject",
 *   conditions?: string[],       // required when decision="approve_with_conditions"
 *   notes?: string
 * }
 *
 * Response: { ok: true, approvalId, status }
 */
hooksRouter.post("/t3-approve", async (req: Request, res: Response) => {
  const body = req.body as {
    approvalId?: unknown;
    sessionId?: unknown;
    decision?: unknown;
    conditions?: unknown;
    notes?: unknown;
  };

  const approvalId = typeof body.approvalId === "string" ? body.approvalId.trim() : "";
  const sessionId  = typeof body.sessionId  === "string" ? body.sessionId.trim()  : "";
  const decision   = typeof body.decision   === "string" ? body.decision.trim()   : "";

  // --- Validate inputs ---
  if (!approvalId) {
    return res.status(400).json({ error: "approvalId is required" });
  }
  if (!sessionId) {
    return res.status(400).json({ error: "sessionId is required" });
  }
  const validDecisions = ["approve", "approve_with_conditions", "reject"];
  if (!validDecisions.includes(decision)) {
    return res.status(400).json({ error: `decision must be one of: ${validDecisions.join(", ")}` });
  }

  const conditions: string[] = Array.isArray(body.conditions)
    ? (body.conditions as unknown[]).filter((c): c is string => typeof c === "string")
    : [];
  const notes = typeof body.notes === "string" ? body.notes.slice(0, 1000) : undefined;

  if (decision === "approve_with_conditions" && conditions.length === 0) {
    return res.status(400).json({ error: "conditions array is required when decision=approve_with_conditions" });
  }

  try {
    const now = new Date().toISOString();
    const status = decision === "reject"
      ? "rejected"
      : decision === "approve_with_conditions"
        ? "approved_with_conditions"
        : "approved";

    // Update the t3_approvals row (upsert via UPDATE — row must already exist)
    const db = (req.app.locals?.db ?? null) as { run?: (sql: string, params: unknown[]) => void } | null;
    if (db?.run) {
      db.run(
        `UPDATE t3_approvals
         SET status = ?, resolved_at = ?, conditions = ?, reviewer_notes = ?
         WHERE id = ? AND session_id = ? AND status = 'pending'`,
        [
          status,
          now,
          conditions.length > 0 ? JSON.stringify(conditions) : null,
          notes ?? null,
          approvalId,
          sessionId,
        ],
      );
    }

    // Emit audit event
    const auditKind = status === "rejected"
      ? ("t3_approval_rejected" as const)
      : ("t3_approval_granted" as const);

    auditLog.write({
      kind: auditKind,
      decision: status,
      sessionId,
      reason: notes,
      meta: {
        approvalId,
        conditions: conditions.length > 0 ? conditions : undefined,
        resolvedAt: now,
      },
    });

    console.info(`[t3-approve] ${status} — approval_id=${approvalId} session=${sessionId}`);
    return res.json({ ok: true, approvalId, status });
  } catch (err) {
    console.error("[t3-approve] Error resolving approval:", err);
    return res.status(500).json({ error: "Internal server error" });
  }
});

/**
 * POST /hooks/t3-pending
 *
 * Registers a new T3 hard stop from the Python task_complete_gate.
 * Creates a t3_approvals row in 'pending' status and emits t3_hard_stop audit event.
 *
 * Body: {
 *   approvalId: string,   // UUID generated by caller
 *   sessionId: string,
 *   traceId?: string,
 *   criteria: string[],   // T3 trigger reasons
 *   tcs?: number,
 *   preMortemScore?: number
 * }
 */
hooksRouter.post("/t3-pending", async (req: Request, res: Response) => {
  const body = req.body as {
    approvalId?: unknown;
    sessionId?: unknown;
    traceId?: unknown;
    criteria?: unknown;
    tcs?: unknown;
    preMortemScore?: unknown;
  };

  const approvalId = typeof body.approvalId === "string" ? body.approvalId.trim() : "";
  const sessionId  = typeof body.sessionId  === "string" ? body.sessionId.trim()  : "";
  const traceId    = typeof body.traceId    === "string" ? body.traceId.trim()    : null;
  const criteria: string[] = Array.isArray(body.criteria)
    ? (body.criteria as unknown[]).filter((c): c is string => typeof c === "string")
    : [];
  const tcs            = typeof body.tcs === "number" ? body.tcs : null;
  const preMortemScore = typeof body.preMortemScore === "number" ? body.preMortemScore : null;

  if (!approvalId) return res.status(400).json({ error: "approvalId is required" });
  if (!sessionId)  return res.status(400).json({ error: "sessionId is required" });
  if (criteria.length === 0) return res.status(400).json({ error: "criteria must be a non-empty array" });

  try {
    const now = new Date().toISOString();
    const db = (req.app.locals?.db ?? null) as { run?: (sql: string, params: unknown[]) => void } | null;
    if (db?.run) {
      db.run(
        `INSERT OR IGNORE INTO t3_approvals
           (id, session_id, trace_id, triggered_at, criteria, tcs, pre_mortem_score, status)
         VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')`,
        [approvalId, sessionId, traceId, now, JSON.stringify(criteria), tcs, preMortemScore],
      );
    }

    auditLog.write({
      kind: "t3_hard_stop",
      decision: "block",
      sessionId,
      reason: `T3 hard stop: ${criteria.join("; ")}`,
      meta: { approvalId, criteria, tcs, preMortemScore, triggeredAt: now },
    });

    console.warn(`[t3-pending] HARD STOP registered — approval_id=${approvalId} session=${sessionId} criteria=${criteria.join(", ")}`);
    return res.json({ ok: true, approvalId, status: "pending" });
  } catch (err) {
    console.error("[t3-pending] Error registering hard stop:", err);
    return res.status(500).json({ error: "Internal server error" });
  }
});

/**
 * GET /hooks/t3-status
 *
 * Returns status for a T3 approval either by approvalId, or the latest
 * approval row for a given sessionId.
 *
 * Query:
 *   approvalId?: string
 *   sessionId?: string
 *
 * Response:
 *   { ok: true, found: boolean, approval?: { ... } }
 */
hooksRouter.get("/t3-status", async (req: Request, res: Response) => {
  const approvalId = typeof req.query.approvalId === "string" ? req.query.approvalId.trim() : "";
  const sessionId = typeof req.query.sessionId === "string" ? req.query.sessionId.trim() : "";

  if (!approvalId && !sessionId) {
    return res.status(400).json({ error: "approvalId or sessionId is required" });
  }

  type T3StatusRow = {
    id: string;
    session_id: string;
    status: string;
    criteria: string;
    tcs: number | null;
    pre_mortem_score: number | null;
    triggered_at: string;
    resolved_at: string | null;
    conditions: string | null;
    reviewer_notes: string | null;
  };

  try {
    const db = (req.app.locals?.db ?? null) as
      | { prepare?: (sql: string) => { get: (...params: unknown[]) => T3StatusRow | undefined } }
      | null;

    if (!db?.prepare) {
      return res.json({ ok: true, found: false });
    }

    const row = approvalId
      ? db.prepare(
          `SELECT id, session_id, status, criteria, tcs, pre_mortem_score,
                  triggered_at, resolved_at, conditions, reviewer_notes
             FROM t3_approvals
            WHERE id = ?
            LIMIT 1`
        ).get(approvalId)
      : db.prepare(
          `SELECT id, session_id, status, criteria, tcs, pre_mortem_score,
                  triggered_at, resolved_at, conditions, reviewer_notes
             FROM t3_approvals
            WHERE session_id = ?
            ORDER BY datetime(triggered_at) DESC, created_at DESC
            LIMIT 1`
        ).get(sessionId);

    if (!row) {
      return res.json({ ok: true, found: false });
    }

    return res.json({
      ok: true,
      found: true,
      approval: {
        approvalId: row.id,
        sessionId: row.session_id,
        status: row.status,
        criteria: (() => {
          try {
            const parsed = JSON.parse(row.criteria);
            return Array.isArray(parsed) ? parsed : [];
          } catch {
            return [];
          }
        })(),
        tcs: row.tcs,
        preMortemScore: row.pre_mortem_score,
        triggeredAt: row.triggered_at,
        resolvedAt: row.resolved_at,
        conditions: (() => {
          if (!row.conditions) return [];
          try {
            const parsed = JSON.parse(row.conditions);
            return Array.isArray(parsed) ? parsed : [];
          } catch {
            return [];
          }
        })(),
        notes: row.reviewer_notes,
      },
    });
  } catch (err) {
    console.error("[t3-status] Error reading approval status:", err);
    return res.status(500).json({ error: "Internal server error" });
  }
});
