/**
 * Ghost substrate types
 * 
 * Defines the typed envelope contracts between:
 * - Raw user input (RawRequestEnvelope)
 * - Normalized intent (CanonicalIntent)
 * - Policy decision (PolicyDecision)
 * - Dispatch to Gen (DispatchEnvelope)
 */

// === REQUEST ENVELOPE (Layer 0 → Layer 1) ===

export interface RawRequestEnvelope {
  /** Unique request ID for tracing */
  requestId: string;
  
  /** Raw user input (unstructured) */
  rawInput: string;
  
  /** Source of request */
  source: "claude_cli" | "metachromatic_ui" | "mcp_client" | "internal_daemon" | "other";
  
  /** Session context if available */
  sessionId?: string;
  
  /** Prior intent hint (from session routing store) */
  priorIntent?: string;
  
  /** E2E tracing metadata */
  metadata?: {
    e2eRunId?: string;
    e2eTags?: string[];
  };
  
  /** Timestamp */
  timestamp: string;
}

// === CANONICAL INTENT (Layer 1 → Layer 2) ===

export type IntentCategory =
  | "debug"                  // "unpack the system", "audit", "review"
  | "code"                   // "write", "refactor", "implement"
  | "generation"             // "generate images", "run batch", "create assets"
  | "delegation"             // "run the task", "execute workflow"
  | "governance"             // "turn off stops", "switch modes", "policy"
  | "status"                 // "what's running", "check status"
  | "explore"                // "search codebase", "find files"
  | "clarification"          // "what do you mean", "explain"
  | "unknown";

export interface CanonicalIntent {
  /** Unique ID for this intent */
  intentId: string;
  
  /** Core intent category */
  primary_intent: IntentCategory;
  
  /** Scope of work */
  scope: "simple" | "medium" | "complex";
  
  /** Explicit keywords extracted from input */
  explicit_keywords: string[];
  
  /** Inferred goals (e.g., "understand-architecture", "validate-safety") */
  implied_goals: string[];
  
  /** Risk markers (e.g., "dangerous_command", "protected_path", "high_token_cost") */
  risk_markers: string[];
  
  /** How ambiguous is this request (0 = clear, 1 = very ambiguous) */
  ambiguity_level: "low" | "medium" | "high";
  
  /** Does this need human approval? */
  requires_policy_review: boolean;
  
  /** Should this be async? */
  suggests_async_dispatch: boolean;
  
  /** Confidence score (0-1) */
  confidence: number;
  
  /** Session context */
  sessionId?: string;
  
  /** Timestamp */
  timestamp: string;
}

// === POLICY DECISION (Layer 2 → Layer 3) ===

export type DispatchDecision =
  | "dispatch_to_gen"           // Send to Gen hooks for execution
  | "dispatch_with_guardrails"  // Send to Gen with extra constraints
  | "return_template"           // Return a fixed response (testing/fallback)
  | "defer"                     // Queue for later (async)
  | "clarify"                   // Ask user for more info
  | "block";                    // Do not execute

export type FallbackMode =
  | "return_cached_or_template"
  | "async_queue"
  | "fail_open"
  | "fail_closed";

export interface PolicyDecision {
  /** Unique ID for this decision */
  decisionId: string;
  
  /** What should happen */
  decision: DispatchDecision;
  
  /** Where to route */
  targetService: "gen" | "internal" | "queue" | "user_feedback";
  
  /** Configuration for dispatch */
  dispatchConfig: {
    responseMode: "normal" | "ollama_gate" | "dummy";
    pretoolStopsEnforced: boolean;
    budgetConstraint: "low" | "medium" | "high";
    expectedLatencyMs: number;
    retryPolicy: "exponential_backoff" | "immediate" | "none";
    maxRetries: number;
  };
  
  /** Fallback strategy if dispatch fails */
  fallbackMode: FallbackMode;
  
  /** What user should see */
  userFeedback?: {
    prefix?: string;      // Message before execution
    suffix?: string;      // Message during/after execution
    onError?: string;     // Message if things fail
  };
  
  /** Tags for audit trail */
  auditTags: string[];
  
  /** Reasoning (for transparency) */
  reasoning?: string;
  
  /** Session tracking */
  sessionId?: string;
  traceId: string;
  
  /** Timestamp */
  timestamp: string;
}

// === DISPATCH ENVELOPE (Layer 3 → Gen) ===

export interface DispatchEnvelope {
  /** Routing to Gen */
  target: "gen";
  
  /** The policy decision that led here */
  policyDecision: PolicyDecision;
  
  /** Tracing */
  sessionId: string;
  traceId: string;
  
  /** Actual payload for Gen */
  userPrompt: string;
  canonicalIntent: CanonicalIntent;
  
  /** Instrumentation */
  acceptedResponseModes: ("normal" | "ollama_gate" | "dummy")[];
  timeoutMs: number;
  retryCount: number;
}

// === RESPONSE FROM GEN ===

export interface GenExecutionResult {
  success: boolean;
  output?: unknown;
  error?: string;
  duration_ms: number;
  tokens_used?: number;
}

// === GHOST INTERNAL STATE SNAPSHOT ===

export interface SystemStateSnapshot {
  pretoolStopsEnforced: boolean;
  responseMode: "normal" | "ollama_gate" | "dummy";
  budgetState?: {
    taskId: string;
    agentRole: string;
    utilizationPct: number;
    tokensRemaining: number;
    isLowBudget: boolean;
  };
  ollamaAvailable: boolean;
  sessionRoutingHint?: {
    intent: string;
    scope: string;
  };
}
