import { nanoid } from "nanoid";
import type { LlmProvider, ClaudeModelTier } from "../llm/llm-types.js";

/**
 * IntentClass and ScopeLevel mirror Spectrum's routing vocabulary.
 * Kept as strings here so this module has no circular dependency on Spectrum.
 */
export type IntentClass = "code" | "explore" | "manage" | "dispatch" | "query" | "review" | "other";
export type ScopeLevel = "simple" | "medium" | "complex";

/**
 * The original user request and Claude's elevated understanding of it.
 * This is the source-of-truth artifact that travels unchanged through every
 * delegation hop. Downstream LLMs receive this verbatim — never summarized,
 * never compressed.
 *
 * Principle: degradation in multi-LLM chains happens because intermediate
 * summaries discard intent. originalPrompt prevents that.
 */
export interface TaskContext {
  /** Unique trace ID — links every delegation attempt back to this context. */
  traceId: string;
  /** Wall-clock time this context was created. */
  createdAt: string;

  // --- Source of truth ---
  /** The user's raw request. NEVER modified. Every downstream LLM sees this. */
  originalPrompt: string;
  /** The tool name that triggered this context (from PreToolUse). */
  toolName: string;

  // --- Claude's elevation ---
  /** Spectrum intent class derived from the tool + input. */
  intentClass: IntentClass;
  /** Complexity estimate. */
  scopeLevel: ScopeLevel;
  /**
   * Optional: Claude's domain-knowledge injection added before delegation.
   * e.g. "This codebase uses X pattern. The caller expects Y format."
   * When set, always prepended to delegated prompts verbatim.
   */
  claudeElevation?: string;
  /** Hard constraints the downstream LLM must honour. */
  constraints?: string[];

  // --- Routing decision ---
  /** Which provider was selected for this task. */
  selectedProvider: LlmProvider;
  /** Specific model ID chosen (e.g. "claude-haiku-4-5-20251001"). */
  selectedModel: string;
  /** For claude provider: the tier selected. */
  claudeTier?: ClaudeModelTier;

  // --- Delegation payload ---
  /**
   * Specific delegated subtask, if different from originalPrompt.
   * When null, the downstream LLM receives originalPrompt directly.
   */
  delegatedTask?: string;
  /** Expected output schema/format. Violations trigger fallback. */
  expectedOutputFormat?: string;
}

/**
 * Builds a prompt string for delegation that always anchors to the original request.
 * Downstream LLMs receive:
 *   1. ORIGINAL REQUEST (verbatim)
 *   2. CONTEXT (Claude's elevation, if any)
 *   3. CONSTRAINTS (hard boundaries)
 *   4. TASK (specific subtask or same as original)
 *   5. OUTPUT FORMAT (if specified)
 */
export function buildDelegationPrompt(ctx: TaskContext): string {
  const parts: string[] = [];

  parts.push(`ORIGINAL REQUEST:\n${ctx.originalPrompt}`);

  if (ctx.claudeElevation) {
    parts.push(`CONTEXT:\n${ctx.claudeElevation}`);
  }

  if (ctx.constraints && ctx.constraints.length > 0) {
    parts.push(`CONSTRAINTS:\n${ctx.constraints.map((c) => `- ${c}`).join("\n")}`);
  }

  if (ctx.delegatedTask && ctx.delegatedTask !== ctx.originalPrompt) {
    parts.push(`TASK:\n${ctx.delegatedTask}`);
  }

  if (ctx.expectedOutputFormat) {
    parts.push(`OUTPUT FORMAT:\n${ctx.expectedOutputFormat}`);
  }

  return parts.join("\n\n---\n\n");
}

/**
 * Creates a new TaskContext with a fresh traceId.
 */
export function createTaskContext(
  params: Omit<TaskContext, "traceId" | "createdAt">,
): TaskContext {
  return {
    traceId: nanoid(12),
    createdAt: new Date().toISOString(),
    ...params,
  };
}
