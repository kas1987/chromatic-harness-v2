/**
 * Classifies task complexity to guide model routing in aggressive budget mode.
 *
 * Simple: single bash call, read/grep/ls operations, echo — typically 0-5K tokens
 * Complex: council spawning, agent dispatch, discovery/research, crank execution — typically >5K tokens
 */

const COMPLEX_KEYWORDS = [
  "council", "agent", "spawn", "discovery", "research", "crank",
  "validation", "multi-step", "orchestrat", "pipeline", "batch",
];

const SIMPLE_TOOLS = ["Read", "Glob", "Grep", "ls", "echo", "cat", "head", "tail"];

export type TaskComplexity = "simple" | "complex";

export interface TaskClassificationInput {
  description?: string;
  toolName?: string;
  commandLength?: number;
}

/**
 * Classify task complexity from description, tool name, or command length.
 *
 * Rules (in priority order):
 * 1. If tool is a read-only tool (Read, Glob, Grep) → simple
 * 2. If description contains complex keywords → complex
 * 3. If commandLength > 500 chars → complex (long commands = complex pipelines)
 * 4. Default → simple
 */
export function classifyTaskComplexity(input: TaskClassificationInput): TaskComplexity {
  // Rule 1: read-only tools are always simple
  if (input.toolName && SIMPLE_TOOLS.includes(input.toolName)) {
    return "simple";
  }

  // Rule 2: keyword detection in description
  if (input.description) {
    const lower = input.description.toLowerCase();
    if (COMPLEX_KEYWORDS.some(kw => lower.includes(kw))) {
      return "complex";
    }
  }

  // Rule 3: long command length suggests complex pipeline
  if (input.commandLength && input.commandLength > 500) {
    return "complex";
  }

  return "simple";
}
