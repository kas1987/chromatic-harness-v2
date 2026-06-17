import { CanonicalIntent, PolicyDecision, SystemStateSnapshot } from "./ghost-types.js";

interface PolicyRule {
  name: string;
  predicate: (intent: CanonicalIntent, state: SystemStateSnapshot) => boolean;
  decision: Omit<PolicyDecision, "decisionId" | "traceId" | "reasoning" | "timestamp">;
}

export class GhostPolicyEngine {
  private rules: PolicyRule[] = [];

  constructor() {
    this.initializeDefaultRules();
  }

  private initializeDefaultRules(): void {
    this.addRule({
      name: "block-low-confidence",
      predicate: (intent) => intent.primary_intent === "unknown" && intent.confidence < 0.3,
      decision: {
        decision: "block",
        targetService: "user_feedback",
        auditTags: ["security"],
        fallbackMode: "fail_closed",
        userFeedback: { prefix: "Cannot understand request. Please be more specific." },
        dispatchConfig: {
          responseMode: "normal",
          pretoolStopsEnforced: true,
          budgetConstraint: "low",
          expectedLatencyMs: 5000,
          retryPolicy: "none",
          maxRetries: 0,
        },
      },
    });

    this.addRule({
      name: "clarify-high-ambiguity",
      predicate: (intent) => intent.ambiguity_level === "high" && !intent.requires_policy_review,
      decision: {
        decision: "clarify",
        targetService: "user_feedback",
        auditTags: ["clarity"],
        fallbackMode: "fail_open",
        userFeedback: { prefix: "Your request is ambiguous. Please clarify." },
        dispatchConfig: {
          responseMode: "normal",
          pretoolStopsEnforced: true,
          budgetConstraint: "low",
          expectedLatencyMs: 60000,
          retryPolicy: "none",
          maxRetries: 0,
        },
      },
    });

    this.addRule({
      name: "defer-complex-generation",
      predicate: (intent, state) =>
        intent.scope === "complex" &&
        intent.primary_intent === "generation" &&
        !state.pretoolStopsEnforced,
      decision: {
        decision: "defer",
        targetService: "queue",
        auditTags: ["batch", "async"],
        fallbackMode: "async_queue",
        userFeedback: { prefix: "Queuing batch job for async execution." },
        dispatchConfig: {
          responseMode: "normal",
          pretoolStopsEnforced: false,
          budgetConstraint: "high",
          expectedLatencyMs: 300000,
          retryPolicy: "exponential_backoff",
          maxRetries: 2,
        },
      },
    });

    this.addRule({
      name: "guardrail-governance",
      predicate: (intent) => intent.primary_intent === "governance" && intent.requires_policy_review,
      decision: {
        decision: "dispatch_with_guardrails",
        targetService: "gen",
        auditTags: ["governance", "safety"],
        fallbackMode: "fail_closed",
        userFeedback: { prefix: "Running governance operation with guardrails." },
        dispatchConfig: {
          responseMode: "normal",
          pretoolStopsEnforced: true,
          budgetConstraint: "low",
          expectedLatencyMs: 30000,
          retryPolicy: "immediate",
          maxRetries: 1,
        },
      },
    });

    this.addRule({
      name: "block-budget-exhausted",
      predicate: (_intent, state) => Boolean(state.budgetState?.isLowBudget && state.budgetState.utilizationPct > 95),
      decision: {
        decision: "block",
        targetService: "user_feedback",
        auditTags: ["budget"],
        fallbackMode: "fail_closed",
        userFeedback: { prefix: "Budget exhausted. Try again later." },
        dispatchConfig: {
          responseMode: "normal",
          pretoolStopsEnforced: true,
          budgetConstraint: "low",
          expectedLatencyMs: 5000,
          retryPolicy: "none",
          maxRetries: 0,
        },
      },
    });

    this.addRule({
      name: "template-dummy-mode",
      predicate: (_intent, state) => state.responseMode === "dummy",
      decision: {
        decision: "return_template",
        targetService: "internal",
        auditTags: ["testing"],
        fallbackMode: "return_cached_or_template",
        dispatchConfig: {
          responseMode: "dummy",
          pretoolStopsEnforced: true,
          budgetConstraint: "low",
          expectedLatencyMs: 100,
          retryPolicy: "none",
          maxRetries: 0,
        },
      },
    });

    this.addRule({
      name: "guardrail-ollama-gate-debug",
      predicate: (intent, state) =>
        state.responseMode === "ollama_gate" && state.ollamaAvailable && intent.primary_intent === "debug",
      decision: {
        decision: "dispatch_with_guardrails",
        targetService: "gen",
        auditTags: ["ollama"],
        fallbackMode: "fail_open",
        userFeedback: { prefix: "Ollama gate validation enabled." },
        dispatchConfig: {
          responseMode: "ollama_gate",
          pretoolStopsEnforced: false,
          budgetConstraint: "medium",
          expectedLatencyMs: 60000,
          retryPolicy: "immediate",
          maxRetries: 1,
        },
      },
    });

    this.addRule({
      name: "default-dispatch",
      predicate: () => true,
      decision: {
        decision: "dispatch_to_gen",
        targetService: "gen",
        auditTags: ["default"],
        fallbackMode: "fail_open",
        dispatchConfig: {
          responseMode: "normal",
          pretoolStopsEnforced: false,
          budgetConstraint: "medium",
          expectedLatencyMs: 30000,
          retryPolicy: "exponential_backoff",
          maxRetries: 1,
        },
      },
    });
  }

  addRule(rule: PolicyRule): void {
    this.rules.unshift(rule);
  }

  decidePolicyForIntent(intent: CanonicalIntent, state: SystemStateSnapshot, traceId: string): PolicyDecision {
    for (const rule of this.rules) {
      if (rule.predicate(intent, state)) {
        return {
          decisionId: `decision-${Date.now()}`,
          ...rule.decision,
          traceId,
          reasoning: `Matched rule: ${rule.name}`,
          timestamp: new Date().toISOString(),
        };
      }
    }

    return {
      decisionId: `decision-${Date.now()}-fallback`,
      decision: "dispatch_to_gen",
      targetService: "gen",
      traceId,
      auditTags: ["fallback"],
      fallbackMode: "fail_open",
      timestamp: new Date().toISOString(),
      dispatchConfig: {
        responseMode: "normal",
        pretoolStopsEnforced: false,
        budgetConstraint: "medium",
        expectedLatencyMs: 30000,
        retryPolicy: "exponential_backoff",
        maxRetries: 1,
      },
    };
  }

  getRuleCount(): number {
    return this.rules.length;
  }

  getRuleNames(): string[] {
    return this.rules.map((r) => r.name);
  }
}

export const ghostPolicyEngine = new GhostPolicyEngine();
