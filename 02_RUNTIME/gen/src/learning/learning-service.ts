/**
 * LearningService — orchestrates outcome recording and pattern computation.
 *
 * Intended usage:
 *   - Call recordToolOutcome() from the PostToolUse hook handler.
 *   - Call getRecommendation() from the PreToolUse hook handler.
 */

import type { LearningStore } from "./learning-store";
import type { AdaptiveRouter } from "./adaptive-router";
import { inferIntent } from "./adaptive-router";
import type { RoutingRecommendation } from "./learning-types";
import type { NateClient } from "../services/nate-client";

export class LearningService {
  constructor(
    private store: LearningStore,
    private router: AdaptiveRouter,
    private nateClient?: NateClient,
  ) {}

  /**
   * Record the outcome of a completed tool use.
   * After every 10 outcomes for a given (agentRole, intent) pair the
   * routing pattern is recomputed and stored.
   */
  async recordToolOutcome(params: {
    taskId: string;
    agentRole: string;
    projectId: string;
    toolName: string;
    input: Record<string, unknown>;
    succeeded: boolean;
    durationMs: number;
    tokensUsed: number;
    errorMessage?: string;
    /** From session routing cache (PromptNormalizer intent). */
    promptIntent?: string;
    promptScope?: string;
    /** Client-reported active LLM for this turn. */
    activeLlm?: string;
    /** Client echo of last pretool suggestedLlm. */
    suggestedLlm?: string;
  }): Promise<void> {
    const intent = inferIntent(params.toolName, params.input);

    // Optionally enrich with Nate context (fail-open, fire-and-forget style)
    let nateContext: string | undefined;
    if (this.nateClient) {
      try {
        const results = await this.nateClient.query(params.toolName, 3);
        if (results.length > 0) {
          nateContext = results.map((r) => r.title).join("; ");
        }
      } catch {
        // Nate unavailable — continue without enrichment
      }
    }

    this.store.recordOutcome({
      taskId: params.taskId,
      agentRole: params.agentRole,
      projectId: params.projectId,
      intent,
      toolUsed: params.toolName,
      succeeded: params.succeeded,
      durationMs: params.durationMs,
      tokensUsed: params.tokensUsed,
      errorMessage: params.errorMessage,
      promptIntent: params.promptIntent,
      promptScope: params.promptScope,
      activeLlm: params.activeLlm,
      suggestedLlm: params.suggestedLlm,
    });

    // Recompute pattern every 10 outcomes (0 % 10 === 0 is handled by the
    // >= 3 guard inside computeAndStorePattern, so it's safe on first call)
    const outcomes = this.store.getOutcomesForIntent(params.agentRole, intent);
    if (outcomes.length >= 3 && outcomes.length % 10 === 0) {
      this.store.computeAndStorePattern(params.agentRole, intent);
    }
  }

  /**
   * Return a routing recommendation for an about-to-execute tool use.
   */
  getRecommendation(
    agentRole: string,
    toolName: string,
    input: Record<string, unknown>,
  ): RoutingRecommendation {
    return this.router.recommend(agentRole, toolName, input);
  }
}
