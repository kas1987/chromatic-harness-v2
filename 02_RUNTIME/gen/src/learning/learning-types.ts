/**
 * Type definitions for the learning / adaptive-routing system
 */

// A recorded outcome from a completed task or tool use
export interface TaskOutcome {
  id: string;                 // nanoid
  taskId: string;
  agentRole: string;
  projectId: string;
  intent: string;             // e.g. "edit_file", "run_tests", "search_code"
  toolUsed: string;           // e.g. "Edit", "Bash", "Glob"
  succeeded: boolean;
  durationMs: number;
  tokensUsed: number;
  errorMessage?: string;
  recordedAt: string;         // ISO timestamp
  /** Session prompt classifier intent when available (from Gen routing cache). */
  promptIntent?: string;
  promptScope?: string;
  /** Client-reported LLM used for the turn (optional). */
  activeLlm?: string;
  /** Echo of Gen pretool `suggestedLlm` when client sends it (optional). */
  suggestedLlm?: string;
}

// An aggregated pattern derived from multiple outcomes
export interface RoutingPattern {
  id: string;
  agentRole: string;
  intent: string;
  preferredTool: string;      // the tool with the highest success rate
  successRate: number;        // 0-1
  avgDurationMs: number;
  sampleCount: number;
  lastUpdatedAt: string;
}

// Decision from the adaptive router
export interface RoutingRecommendation {
  suggestedTool?: string;     // present when a pattern exists with successRate >= 0.7
  confidence: number;         // 0-1
  reason: string;             // human-readable explanation
  warningMessage?: string;    // present when similar intent has a high failure rate
}
