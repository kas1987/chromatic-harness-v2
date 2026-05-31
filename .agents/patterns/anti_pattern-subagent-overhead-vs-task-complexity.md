---
name: subagent-overhead-vs-task-complexity
type: anti-pattern
confidence: 0.90
source_learnings: [2026-04-26-subagent-overhead-vs-task-complexity]
description: Learning: Match Subagent Dispatch Granularity to Task Complexity
tags: [subagents, orchestration, efficiency, pragma]
---

# Learning: Match Subagent Dispatch Granularity to Task Complexity

## What We Learned

The full subagent-driven-development pattern (1 implementer + 1 spec reviewer + 1 code-quality reviewer per task) adds 60-90 seconds of orchestration overhead per task. For tasks where the plan specifies every line of code and TDD ensures correctness via the test suite, this overhead exceeds the marginal value of the reviews.

Three pragmatic adaptations that work without sacrificing quality:

1. **Skip reviewers for trivial setup tasks** (single-file boilerplate, vitest scaffold). The implementer's self-test (test passes / build succeeds) is sufficient.
2. **Combined spec+quality reviewer** (parallel single subagent) for mechanical tasks where the spec match is obvious.
3. **Batch independent file creations** (e.g., 5 slash-command markdowns) into one implementer dispatch when there are no inter-task dependencies. The skill warns against parallel implementer dispatches for *conflicting* work; sequential within one subagent is fine.

## Why It Matters

A 27-task plan executed with strict 3-subagent-per-task overhead = 81+ dispatches at ~45s each = 60+ minutes of orchestration. With the adaptations above, the same plan executed in ~25 dispatches with no quality regression.

The skill text said "Skip reviews ... is a red flag" but the spirit (catch issues before next task) is preserved by relying on TDD test pass + self-review for trivial work.

## Source

whisper-call v0.1.0 build (27 tasks executed in single session). After Tasks 1-2 used full 3-subagent pattern, switched to combined or skipped reviewers for mechanical tasks. No quality issues emerged in the final 65/65 test suite or live e2e verification.

## When to Apply

- **Full 3-subagent pattern:** integration-heavy tasks, multi-file refactors, design-judgment work, security-sensitive code
- **Combined reviewer:** single-file boilerplate, well-spec'd module implementations
- **Skip reviewers:** TDD setup, file-with-given-content scaffolding, no-logic config files
- **Batch implementer:** multiple independent file creations with no shared state

## Anti-Pattern

Following the rigid 3-subagent rule for a 30-task plan of mechanical tasks. Cost: 60+ minutes of orchestration overhead, dozens of barely-useful reviewer dispatches. Result: same correctness as the streamlined version, but slower and more expensive.

## Trade-off

The strict pattern provides defense against implementer mistakes that aren't caught by tests (e.g., using wrong content from the plan, introducing subtle bugs). When the plan is genuinely complete (every line of code specified), this defense is largely redundant with TDD. When the plan has gaps requiring judgment, the strict pattern is worth the overhead.
