/**
 * Hop (Bell Hop) — Dispatch skill type definitions.
 *
 * Hop is a dual-trigger Express middleware that intercepts the gen/ user-prompt
 * hook before LLM selection fires, routing dispatch-intent messages to local skills
 * or remote MCPs via a priority-ordered routing table (hop-routes.json).
 *
 * Activation contract: Hop ONLY activates when the source explicitly sets
 * metadata.intent_tag in the request body. Normal Claude Code prompts pass through
 * untouched.
 */

export type HopDispatchType = "local" | "remote_mcp";
export type HopDispatchMode = "async" | "sync";

/**
 * A single routing rule from hop-routes.json.
 * Rules are evaluated in priority order (lower number = higher priority).
 * First matching rule wins.
 */
export interface HopRoute {
  rule_id: string;
  priority: number;
  source_skill?: string;       // match originating skill name (optional)
  intent_tag?: string;         // match IntentClass value (optional)
  payload_pattern?: string;    // regex match against prompt text (optional)
  destination: string;         // skill name or MCP tool name
  destination_type: HopDispatchType;
  confidence_floor: number;    // 0.0–1.0; rule skipped if envelope confidence below this
  dispatch_mode: HopDispatchMode;
  prompt_rewrite_template?: string; // "Execute via {{destination}}: {{payload}}"
  metadata_tags?: string[];
  /** When destination_type is remote_mcp, optional path segment under GEN_HOP_REMOTE_MCP_URL */
  mcp_forward_path?: string;
}

/** Set on Express Request when Hop matches a route (same request as /hooks/user-prompt). */
export interface HopDispatchContext {
  hop_id: string;
  rule_id: string;
  destination: string;
  dispatch_mode: HopDispatchMode;
}

/**
 * The message envelope that travels through Hop.
 * Built from the incoming request and enriched with routing context.
 */
export interface HopEnvelope {
  hop_id: string;              // UUID, idempotency key
  source_skill?: string;
  payload: string;             // original or rewritten prompt
  intent_tag?: string;
  session_id?: string;
  timestamp: string;           // ISO 8601
  confidence: number;          // 0.0–1.0
  route?: HopRoute;            // resolved route (undefined = dead-letter)
  dead_lettered: boolean;
  metadata: Record<string, unknown>;
}

/**
 * Result returned after Hop completes routing (success or dead-letter).
 */
export interface HopResult {
  hop_id: string;
  routed: boolean;
  destination?: string;
  dispatch_mode?: HopDispatchMode;
  confidence: number;
  dead_lettered: boolean;
  duration_ms: number;
}
