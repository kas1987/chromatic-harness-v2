export const GEN_ATTRS = {
  AGENT_ID: "gen.agent_id",
  AGENT_ROLE: "gen.agent_role",
  PROJECT_ID: "gen.project_id",
  TASK_ID: "gen.task_id",
  SESSION_ID: "gen.session_id",
  WORKFLOW_ID: "gen.workflow_id",
  TOOL_NAME: "gen.tool_name",
  /** Post-tool hook: whether the client reported tool success (span only; keep off metric labels). */
  TOOL_SUCCESS: "gen.tool_success",
  HOOK_EVENT: "gen.hook_event",
  DECISION: "gen.decision",
  STOP_REASON: "gen.stop_reason",
  MEMORIES_RETURNED: "gen.memories_returned",
  EMBEDDING_CACHE_HIT: "gen.embedding_cache_hit",
  BUDGET_ACTION: "gen.budget_action",
  TOKENS_USED: "gen.tokens_used",
  MEMORY_SCOPE: "gen.memory_scope",
  MEMORY_SENSITIVITY: "gen.memory_sensitivity",
  INTENT: "gen.intent",
  SCOPE: "gen.scope",
  /** Resolved LLM provider recommendation on `hook.pretool` / `hook.user-prompt` (low cardinality). */
  SUGGESTED_LLM: "gen.suggested_llm",
  /**
   * Pretool only: why routing hints were chosen.
   * Values: `read_only_tool` | `session_intent` | `default` | `error_fallback` | `selector_unavailable`
   */
  PRETOOL_ROUTING_SOURCE: "gen.pretool_routing_source",
  /** Client-reported provider actually used for the turn (optional); low cardinality. */
  ACTUAL_LLM: "gen.actual_llm",
  /**
   * Pretool: comparison of suggested vs client-reported actual.
   * Values: `match` | `mismatch` | `unknown` (no client report)
   */
  ROUTING_RECONCILIATION: "gen.routing_reconciliation",
  /** Pretool: true when session routing cache had a valid hint for this sessionId. */
  SESSION_ROUTING_HIT: "gen.session_routing_hit",
  /**
   * Pretool when session_intent: age of cached hint since user-prompt set it.
   * Values: `0-30s` | `30s-2m` | `2m-5m`
   */
  SESSION_HINT_AGE_BUCKET: "gen.session_hint_age_bucket",
  /** Prompt normalizer / intent classifier version string. */
  PROMPT_NORMALIZER_VERSION: "gen.prompt_normalizer_version",
  /**
   * Posttool: session prompt intent vs heavy tool use (coarse meta check).
   * Values: `aligned` | `mismatch_soft` | `unknown`
   */
  INTENT_TOOL_COHERENCE: "gen.intent_tool_coherence",
  /** Posttool / pretool stop: coarse policy bucket for audits. */
  POLICY_LAYER: "gen.policy_layer",
  E2E_RUN_ID: "gen.e2e_run_id",
  E2E_TAGS: "gen.e2e_tags",
} as const;
