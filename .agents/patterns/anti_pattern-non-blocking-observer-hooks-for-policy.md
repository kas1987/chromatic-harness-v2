---
name: non-blocking-observer-hooks-for-policy
type: anti-pattern
confidence: 0.90
source_learnings: [2026-04-26-non-blocking-observer-hooks-for-policy]
description: Learning: Non-Blocking Observer Hooks for Policy Decisions
tags: [hooks, observer-pattern, separation-of-concerns, policy-vs-enforcement]
---

# Learning: Non-Blocking Observer Hooks for Policy Decisions

## What We Learned

When you want to influence a runtime's behavior but the runtime won't accept your custom directives (fixed enums, sealed APIs, no extension points), use a **non-blocking observer hook** that publishes recommendations to a sidecar log, then build a separate **downstream consumer** that acts on those recommendations.

This is the observer + reactor split:
- **Observer hook** (PreToolUse/equivalent): inspects the call, classifies it, writes a structured recommendation, exits 0
- **Downstream consumer** (file watcher / SDK middleware / proxy): reads recommendations, takes action at a layer it controls

## Why It Matters

Claude Code's `Agent` tool only accepts `model: haiku|sonnet|opus`. We wanted to route some dispatches to a local Ollama layer. Rewriting `model: "ol-local"` would have crashed every Agent call. Instead, the hook annotates each call with a recommendation in `~/.claude/.agents/router/log.jsonl`. The Ollama layer (which can't easily inject itself into Claude Code's model selection) watches the log and routes at its own integration point (proxy, SDK swap, etc.).

The same pattern applies anytime you can observe but not modify:
- Tool runtimes with fixed parameter enums
- SaaS APIs you can't fork
- Codebases where adding a config knob requires PR + review + deploy

## Pattern Summary

```
+--------------------+     reads stdin       +-----------------------+
| Runtime (Claude    | --------------------> | Observer hook (.sh)   |
| Code, etc.)        |                       | - classifies          |
|                    |   passes through      | - writes JSONL        |
|                    | <-------------------- | - exits 0 always      |
+--------------------+                       +-----------------------+
                                                       |
                                                       v
                                             +-----------------------+
                                             | Sidecar log           |
                                             | (.agents/router/      |
                                             |  log.jsonl)           |
                                             +-----------------------+
                                                       ^
                                                       | tail -f / poll
                                                       |
                                             +-----------------------+
                                             | Downstream consumer   |
                                             | (file watcher, proxy, |
                                             |  SDK middleware)      |
                                             +-----------------------+
```

## Key Properties

1. **Non-blocking:** hook always exits 0. Never break the runtime.
2. **Idempotent observation:** logging the same call multiple times is safe; consumer dedupes if needed.
3. **Decoupled actor:** hook doesn't know if/when/how the consumer acts. Consumer can be added/removed/replaced independently.
4. **Auditable retroactively:** even without a consumer, the log proves what would have been routed (great for cost-savings projections).
5. **Fails open:** if the consumer is down, runtime keeps working. Worst case: lost optimization, not lost functionality.

## When To Apply

- Influencing runtime behavior you can't directly modify (fixed APIs)
- Adding optional optimizations without risking the critical path
- Building cost/policy/compliance observers without rewriting the runtime
- A/B testing routing decisions before committing to enforcement

## Anti-Patterns

1. **Trying to rewrite parameters with fixed enums.** If `model` only accepts `haiku|sonnet|opus`, don't write `ol-local` — the runtime will reject the entire call.
2. **Hook with side effects beyond logging.** Network calls, slow I/O, or anything that can fail. Hooks should be <5s and never crash.
3. **Synchronous coupling to the consumer.** The hook should not wait for the consumer to confirm. Fire-and-forget JSONL append.
4. **Pattern lists that grow unbounded.** When the classification grammar gets large, externalize to a config file the hook reads.

## Source

`~/.claude/hooks/model-router.sh` (commit `0733c74`). Companion to the cloud-vs-local routing learning (`2026-04-26-cloud-vs-local-routing-strategy.md`). The hook's design constraint — Claude Code's fixed model enum — forced the observer split.
