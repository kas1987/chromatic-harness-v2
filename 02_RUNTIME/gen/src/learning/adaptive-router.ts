/**
 * AdaptiveRouter — uses historical RoutingPatterns to suggest tools
 * and surface warnings about high-failure-rate intents.
 */

import type { LearningStore } from "./learning-store";
import type { RoutingRecommendation } from "./learning-types";

// ---------------------------------------------------------------------------
// Intent inference
// ---------------------------------------------------------------------------

/**
 * Derive a stable, lowercase intent string from a tool name and its input.
 *
 * Intents are intentionally coarse so that enough samples accumulate quickly.
 */
export function inferIntent(
  toolName: string,
  input: Record<string, unknown>,
): string {
  switch (toolName) {
    case "Bash": {
      const cmd = typeof input.command === "string" ? input.command.trim() : "";
      if (/\bnpm\s+(test|run\s+test|vitest|jest)\b/.test(cmd)) return "run_tests";
      if (/\bvitest\b/.test(cmd)) return "run_tests";
      if (/\bgit\s+commit\b/.test(cmd)) return "git_commit";
      if (/\bgit\s+/.test(cmd)) return "git_operation";
      if (/\bnpm\s+/.test(cmd)) return "npm_operation";
      return "bash_command";
    }
    case "Edit":
      return "edit_file";
    case "MultiEdit":
      return "edit_file";
    case "Write":
      return "write_file";
    case "Glob":
      return "search_files";
    case "Grep":
      return "search_content";
    case "Read":
      return "read_file";
    case "WebFetch":
      return "web_fetch";
    default:
      return "tool_use";
  }
}

// ---------------------------------------------------------------------------
// AdaptiveRouter
// ---------------------------------------------------------------------------

export class AdaptiveRouter {
  constructor(private store: LearningStore) {}

  /**
   * Given a tool-use event, return a routing recommendation.
   *
   * Decision ladder:
   *   1. No pattern → { confidence: 0, reason: "No data yet" }
   *   2. successRate < 0.3  → warning
   *   3. successRate >= 0.7 → suggestedTool = pattern.preferredTool
   *   4. Otherwise          → neutral recommendation
   */
  recommend(
    agentRole: string,
    toolName: string,
    input: Record<string, unknown>,
  ): RoutingRecommendation {
    const intent = inferIntent(toolName, input);
    const pattern = this.store.getPattern(agentRole, intent);

    if (!pattern) {
      return {
        confidence: 0,
        reason: "No data yet",
      };
    }

    if (pattern.successRate < 0.3) {
      return {
        confidence: pattern.successRate,
        reason: `Low historical success rate for "${intent}" (${(pattern.successRate * 100).toFixed(0)}% across ${pattern.sampleCount} samples)`,
        warningMessage: `Warning: "${intent}" has a ${(pattern.successRate * 100).toFixed(0)}% success rate for role "${agentRole}". Consider an alternative approach.`,
      };
    }

    if (pattern.successRate >= 0.7) {
      return {
        suggestedTool: pattern.preferredTool,
        confidence: pattern.successRate,
        reason: `Pattern match: "${intent}" succeeds ${(pattern.successRate * 100).toFixed(0)}% of the time with ${pattern.preferredTool} (${pattern.sampleCount} samples)`,
      };
    }

    // 0.3 <= successRate < 0.7 — not enough signal either way
    return {
      confidence: pattern.successRate,
      reason: `Mixed results for "${intent}": ${(pattern.successRate * 100).toFixed(0)}% success rate across ${pattern.sampleCount} samples`,
    };
  }
}
