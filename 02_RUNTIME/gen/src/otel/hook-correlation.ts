import type { Span } from "@opentelemetry/api";
import { GEN_ATTRS } from "./attributes";

export type HookCorrelationInput = {
  sessionId?: string;
  taskId?: string;
  workflowId?: string;
  tool?: string;
  agentRole?: string;
  projectId?: string;
};

/**
 * Sets correlation attributes on a hook span when values are non-empty strings.
 * Use for traces only — do not copy these fields onto metric labels (high cardinality).
 */
export function applyHookCorrelationAttributes(span: Span, ctx: HookCorrelationInput): void {
  const s = ctx.sessionId?.trim();
  if (s) span.setAttribute(GEN_ATTRS.SESSION_ID, s);
  const t = ctx.taskId?.trim();
  if (t) span.setAttribute(GEN_ATTRS.TASK_ID, t);
  const w = ctx.workflowId?.trim();
  if (w) span.setAttribute(GEN_ATTRS.WORKFLOW_ID, w);
  const tool = ctx.tool?.trim();
  if (tool) span.setAttribute(GEN_ATTRS.TOOL_NAME, tool);
  const ar = ctx.agentRole?.trim();
  if (ar) span.setAttribute(GEN_ATTRS.AGENT_ROLE, ar);
  const p = ctx.projectId?.trim();
  if (p) span.setAttribute(GEN_ATTRS.PROJECT_ID, p);
}
