/**
 * Ghost Intake Normalizer
 * Layer 1: Converts raw user requests to structured, classified CanonicalIntent
 *
 * Responsibility: Take ambiguous user language ("can you unpack and we /rpi the Inject system")
 * and normalize to typed CanonicalIntent with:
 * - primary_intent category (debug, code, generation, etc.)
 * - scope assessment (simple, medium, complex)
 * - explicit keywords and implied goals extracted
 * - risk markers identified
 * - ambiguity level calculated
 */

import {
  RawRequestEnvelope,
  CanonicalIntent,
  IntentCategory,
} from "./ghost-types.js";

/**
 * Intent classification vocabulary.
 * Keywords map to primary_intent categories and confidence scoring.
 */
const INTENT_KEYWORDS = {
  debug: {
    keywords: ["debug", "fix", "troubleshoot", "unpack", "diagnose", "trace", "breakpoint", "step", "inspect"],
    confidence: 0.9,
  },
  code: {
    keywords: ["write", "implement", "create", "build", "refactor", "generate", "function", "class", "method", "module"],
    confidence: 0.85,
  },
  generation: {
    keywords: ["generate", "batch", "render", "queue", "produce", "create images", "checkpoint", "seed", "lora"],
    confidence: 0.88,
  },
  governance: {
    keywords: ["audit", "governance", "policy", "rule", "constraint", "lock", "enforce", "compliance"],
    confidence: 0.87,
  },
  delegation: {
    keywords: ["delegate", "dispatch", "send", "route", "forward", "executor", "job", "task", "workflow"],
    confidence: 0.86,
  },
  status: {
    keywords: ["status", "health", "check", "how many", "what's", "are you", "metrics", "report"],
    confidence: 0.8,
  },
  explore: {
    keywords: ["explore", "list", "find", "search", "analyze", "review", "examine", "map", "discover"],
    confidence: 0.82,
  },
  clarification: {
    keywords: ["clarify", "explain", "what", "why", "how", "help", "understand", "can you"],
    confidence: 0.75,
  },
};

/**
 * Risk marker vocabulary.
 * Flags commands, paths, and patterns that require governance review.
 */
const RISK_MARKERS = {
  dangerous_commands: [
    "rm -rf",
    "git reset --hard",
    "git push --force",
    "drop table",
    "delete from",
    "truncate",
    "format",
    "wipe",
    "destroy",
    "kill",
  ],
  protected_paths: [".env", ".pem", ".key", "id_rsa", "credentials", "secret", "token", "password"],
  high_token_patterns: [
    "batch",
    "concurrent",
    "loop",
    "for each",
    "parallel",
    "all files",
    "every",
    "massive",
    "large scale",
  ],
  auth_patterns: ["login", "password", "credential", "oauth", "jwt", "token", "authenticate"],
  data_mutation: ["delete", "drop", "truncate", "clear", "erase", "remove", "overwrite"],
  external_access: ["fetch", "curl", "http", "api", "external", "web", "scrape"],
};

/**
 * Implied goals inferred from pattern detection.
 * Maps keywords/patterns to likely user intent.
 */
const IMPLIED_GOAL_PATTERNS = {
  "understand-architecture": ["architecture", "system", "design", "diagram", "how does", "structure", "topology"],
  "validate-correctness": ["test", "validate", "check", "verify", "assert", "ensure", "correct"],
  "optimize-performance": ["fast", "slow", "performance", "latency", "throughput", "optimize", "profile"],
  "fix-bug": ["bug", "error", "fail", "crash", "break", "issue", "problem", "fix"],
  "audit-compliance": ["audit", "compliance", "governance", "policy", "rule", "lock"],
  "implement-feature": ["feature", "add", "new", "support", "enable", "capability"],
  "manage-state": ["state", "database", "cache", "memory", "disk", "persist"],
};

/**
 * Classify raw user input to IntentCategory.
 * Returns the highest-confidence matching category or "unknown".
 */
function classifyIntent(rawInput: string): { category: IntentCategory; confidence: number } {
  const lowerInput = rawInput.toLowerCase();
  let bestCategory: IntentCategory = "unknown";
  let bestConfidence = 0;

  for (const [category, { keywords, confidence }] of Object.entries(INTENT_KEYWORDS)) {
    const matches = keywords.filter((kw) => lowerInput.includes(kw)).length;
    if (matches > 0) {
      const adjustedConfidence = Math.min(confidence, 0.95 * (1 + matches * 0.1)); // bonus for multiple matches
      if (adjustedConfidence > bestConfidence) {
        bestConfidence = adjustedConfidence;
        bestCategory = category as IntentCategory;
      }
    }
  }

  return { category: bestCategory, confidence: bestConfidence };
}

/**
 * Determine request scope (simple, medium, complex) based on input signals.
 */
function determineScope(rawInput: string): "simple" | "medium" | "complex" {
  const length = rawInput.length;
  const lines = rawInput.split("\n").length;
  const complexity_signals = [
    rawInput.includes("&&"),
    rawInput.includes("|"),
    rawInput.includes("for "),
    rawInput.includes("loop"),
    rawInput.includes("concurrent"),
    rawInput.includes("parallel"),
    rawInput.includes("batch"),
    rawInput.includes("multiple"),
    rawInput.includes("all "),
    length > 500,
    lines > 5,
  ];

  const complexity_count = complexity_signals.filter(Boolean).length;

  if (complexity_count >= 4 || length > 500) return "complex";
  if (complexity_count >= 2 || length > 250) return "medium";
  return "simple";
}

/**
 * Extract explicit keywords from raw input.
 */
function extractKeywords(rawInput: string): string[] {
  const lowerInput = rawInput.toLowerCase();
  const keywords = new Set<string>();

  // Add all recognized intent keywords found in input
  for (const { keywords: intentKeywords } of Object.values(INTENT_KEYWORDS)) {
    for (const kw of intentKeywords) {
      if (lowerInput.includes(kw)) {
        keywords.add(kw);
      }
    }
  }

  // Add all recognized risk markers found in input
  for (const markerList of Object.values(RISK_MARKERS)) {
    for (const marker of markerList) {
      if (lowerInput.includes(marker)) {
        keywords.add(marker);
      }
    }
  }

  return Array.from(keywords);
}

/**
 * Infer likely user goals from input patterns.
 */
function inferGoals(rawInput: string): string[] {
  const lowerInput = rawInput.toLowerCase();
  const goals = new Set<string>();

  for (const [goal, patterns] of Object.entries(IMPLIED_GOAL_PATTERNS)) {
    const matches = patterns.filter((p) => lowerInput.includes(p)).length;
    if (matches >= 1) {
      goals.add(goal);
    }
  }

  return Array.from(goals);
}

/**
 * Identify risk markers present in raw input.
 * Returns list of risk categories with specific matches.
 */
function identifyRisks(rawInput: string): string[] {
  const lowerInput = rawInput.toLowerCase();
  const risks = new Set<string>();

  for (const [category, markers] of Object.entries(RISK_MARKERS)) {
    for (const marker of markers) {
      if (lowerInput.includes(marker)) {
        risks.add(`${category}:${marker}`);
      }
    }
  }

  return Array.from(risks);
}

/**
 * Calculate ambiguity level (low/medium/high).
 * High ambiguity: vague pronouns, unclear intent, conflicting signals.
 */
function calculateAmbiguity(rawInput: string): "low" | "medium" | "high" {
  const lowerInput = rawInput.toLowerCase();
  let ambiguity = 0;

  // Vague pronoun patterns ("we", "they", "it")
  const vague_pronouns = (lowerInput.match(/\bwe\b|\bthey\b|\bit\b/gi) || []).length;
  ambiguity += Math.min(vague_pronouns * 0.15, 0.3);

  // Question-only format without clear action
  const is_question_only = lowerInput.startsWith("can you") || lowerInput.startsWith("could you");
  if (is_question_only && rawInput.split(" ").length < 8) {
    ambiguity += 0.2;
  }

  // Conflicting intent signals (e.g., both "generate" and "debug")
  let intent_count = 0;
  for (const keywords of Object.values(INTENT_KEYWORDS)) {
    const found = keywords.keywords.filter((kw) => lowerInput.includes(kw)).length;
    if (found > 0) intent_count++;
  }
  if (intent_count > 2) {
    ambiguity += 0.15;
  }

  // Short/vague input
  if (rawInput.split(" ").length < 5) {
    ambiguity += 0.1;
  }

  ambiguity = Math.min(ambiguity, 1);

  // Convert numeric ambiguity (0-1) to categorical ("low", "medium", "high")
  if (ambiguity >= 0.6) return "high";
  if (ambiguity >= 0.3) return "medium";
  return "low";
}

/**
 * Normalize raw user request to CanonicalIntent.
 * This is the entry point for the Ghost intake layer.
 *
 * @example
 * normalizeIntent({
 *   requestId: "req-123",
 *   rawInput: "can you unpack and we /rpi the Inject system",
 *   source: "claude_cli",
 *   sessionId: "sess-456",
 *   metadata: {}
 * })
 * // => {
 * //   primary_intent: "debug",
 * //   scope: "medium",
 * //   explicit_keywords: ["unpack", "debug", "inject"],
 * //   implied_goals: ["understand-architecture"],
 * //   risk_markers: [],
 * //   ambiguity_level: 0.22,
 * //   requires_policy_review: false,
 * //   suggests_async_dispatch: false,
 * //   confidence: 0.85
 * // }
 */
export function normalizeIntent(envelope: RawRequestEnvelope): CanonicalIntent {
  const { rawInput, sessionId, timestamp } = envelope;

  const { category: primary_intent, confidence } = classifyIntent(rawInput);
  const scope = determineScope(rawInput);
  const explicit_keywords = extractKeywords(rawInput);
  const implied_goals = inferGoals(rawInput);
  const risk_markers = identifyRisks(rawInput);
  const ambiguity_level = calculateAmbiguity(rawInput);

  // Heuristics for policy review and async dispatch
  const requires_policy_review = risk_markers.length > 0 || confidence < 0.7;
  const suggests_async_dispatch = scope === "complex" || ambiguity_level === "high";

  return {
    intentId: `intent-${Date.now()}-${Math.random().toString(36).substring(7)}`,
    primary_intent,
    scope,
    explicit_keywords,
    implied_goals,
    risk_markers,
    ambiguity_level,
    requires_policy_review,
    suggests_async_dispatch,
    confidence,
    sessionId,
    timestamp,
  };
}

/**
 * Ghost intake service.
 * Handles full normalization pipeline with caching and metrics.
 */
export class GhostIntake {
  private cache = new Map<string, CanonicalIntent>();

  /**
   * Process a raw request envelope through the intake normalizer.
   * Caches results by sessionId to avoid re-classification.
   */
  process(envelope: RawRequestEnvelope): CanonicalIntent {
    const cacheKey = `${envelope.sessionId}:${envelope.rawInput}`;

    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey)!;
    }

    const intent = normalizeIntent(envelope);
    this.cache.set(cacheKey, intent);

    // Prune cache if too large (keep last 1000 intents per session)
    if (this.cache.size > 10000) {
      const entriesToDelete = Array.from(this.cache.keys()).slice(0, 2000);
      for (const key of entriesToDelete) {
        this.cache.delete(key);
      }
    }

    return intent;
  }

  /**
   * Clear intake cache (useful for testing).
   */
  clearCache(): void {
    this.cache.clear();
  }

  /**
   * Get cache stats for debugging.
   */
  getCacheStats(): { size: number } {
    return { size: this.cache.size };
  }
}

// Export singleton instance
export const ghostIntake = new GhostIntake();
