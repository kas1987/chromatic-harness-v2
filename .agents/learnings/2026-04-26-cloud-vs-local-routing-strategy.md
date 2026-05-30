---
id: learning-2026-04-26-cloud-vs-local-routing-strategy
type: learning
date: 2026-04-26
category: process
confidence: high
maturity: provisional
tags: [routing, ollama, cost-optimization, subagents, ol-layer]
---

# Learning: Cloud vs Local (Ollama) Routing Strategy

## What We Learned

This session: **350 model turns, $266 Opus + $0.42 Haiku, 90.7% cache hit rate.** Audit of the Opus turns shows ~30-40% could have routed to local Ollama with no quality loss, saving ~$80-100. The remaining 60-70% genuinely needed Opus reasoning.

The trick is classifying **per-turn**, not per-feature, because the same skill (`subagent-driven-development`) calls Opus for both judgment work (architecture decisions) and mechanical work (write file X with content Y).

## Routing Taxonomy

### → Local (Ollama, e.g., qwen2.5-coder:14b, llama3.1:8b)

**Mechanical implementation:** Plan specifies every line of code; subagent's job is to type it accurately and run tests.

| Pattern | Examples in this session |
|---|---|
| Scaffold-from-template | Tasks 1, 2, 3, 13 (package.json, tsconfig, plugin.json, README) |
| File-with-given-content | Tasks 19-22 (5 slash command markdowns), Task 24 (7 seed templates) |
| Spec-reviewer for trivial tasks | Tasks 1-3 reviewer dispatches (combined later as inefficient) |
| Code quality reviewer for boilerplate | Same — produced "approved with minor observations" 3× in a row |
| Markdown frontmatter parsing / linting | Template loader work, ao forge invocations |
| Test execution + result parsing | Every `npm test` / `pytest` invocation followed by "5/5 passing" report |
| Status formatting / report generation | "5/27 done" updates, JSON-to-table rendering |
| Knowledge extraction (forge) | `ao forge markdown` — local model can decide if a doc is a "decision" vs "knowledge" |

**Heuristic:** If the prompt is >70% reference material (code blocks the agent must copy verbatim) and <30% judgment (decisions to make), route local.

### → Cloud (Opus 4.7 / Sonnet 4.6)

**Judgment-heavy work:** novel decisions, architectural tradeoffs, multi-file integration reasoning.

| Pattern | Examples in this session |
|---|---|
| Brainstorming + design tradeoffs | The whole `superpowers:brainstorming` flow — Q1-Q9 were Opus calls |
| Plan writing (not following) | The 27-task plan creation; the v0.2 plan creation |
| Pre-mortem / risk analysis | Discovery phase for v0.2 — evaluating 3 candidates |
| Spec compliance for integration tasks | Tasks 9, 10, 11, 18 reviews (multi-module integration) |
| Debugging novel issues | The MCP-stdio-hang root cause analysis |
| Cross-file refactor decisions | The `_mcp_call` Popen lifecycle design |
| Conversation steering / tool routing | The orchestrator decisions (when to dispatch, when to inline) |

**Heuristic:** If the prompt asks for a novel decision, comparison of options, or analysis of unfamiliar code, route cloud.

### → Neither (no LLM needed at all)

These were sometimes wrapped in LLM calls in the session but shouldn't be:

| Pattern | Better solution |
|---|---|
| `ls`, `grep`, `git status`, `git log` | Direct shell, no LLM |
| File existence checks | Direct shell |
| JSON pretty-print, YAML validation | `jq`, `yq` |
| Markdown frontmatter parse | Existing `template_loader.py` |
| Test runner invocation | Direct shell |
| Audit log JSONL append | Existing `audit_log.py` |

## Routing Mechanism (concrete suggestion for your OL layer)

Three integration points that match your existing infra:

### 1. PreToolUse hook router

Add a `model-router.sh` PreToolUse hook (alongside `yolo-guard.sh`) that inspects the agent's intended `subagent_type` and `model` parameter. If the task fits the local-routing heuristic, rewrite the request to point at your OL endpoint.

```bash
# ~/.claude/hooks/model-router.sh — sketch
input=$(cat)
tool=$(echo "$input" | jq -r '.tool_name')
sub_type=$(echo "$input" | jq -r '.tool_input.subagent_type // ""')
description=$(echo "$input" | jq -r '.tool_input.description // ""')

if [ "$tool" = "Agent" ]; then
  if echo "$description" | grep -qiE "(scaffold|seed templates|slash command|markdown|README|frontmatter)"; then
    # Rewrite model parameter to OL endpoint sentinel
    echo "$input" | jq '.tool_input.model = "ol-local"'
    exit 0
  fi
fi
echo "$input"
```

The OL layer would need to recognize the `ol-local` sentinel and reroute.

### 2. Subagent-type-based routing in CLAUDE.md

Add a memory note to your global CLAUDE.md so the orchestrator self-routes:

```markdown
## Model routing for subagents

- Mechanical implementer (file-with-given-content, scaffold, run-test-report-result): use local OL via `model: "ol-fast"`
- Judgment implementer (multi-file integration, design decisions): use `model: "sonnet"` or `"opus"`
- Spec compliance reviewer: use `model: "ol-fast"` for boilerplate tasks, `"haiku"` for module-level, `"sonnet"` for multi-file
- Code quality reviewer: same as spec reviewer
- Brainstorm / plan / discovery: ALWAYS cloud (`"opus"` or `"sonnet"`)
```

The orchestrator (me) reads this and passes the right `model` parameter at dispatch time.

### 3. Slash command variants

For user-facing commands, expose explicit local variants:

- `/local-implement <task>` → routes to OL
- `/implement <task>` → routes to cloud (current default)
- `/local-call template list` → reads filesystem, no LLM
- `/call template list` → same (template ops never need LLM in any case)

This gives you per-invocation control when you know a task is mechanical.

## What I observed this session that you can codify

1. **Cache invalidation kills routing economics.** This session's 90.7% cache hit rate is what kept it under $300. If you route 30% of turns to local but break the cache prefix on the cloud-side, you can lose more in cache misses than you save in local routing. **Mitigation:** keep cloud-side conversation linear and contiguous; route to local via ephemeral side-channels (subagent dispatches, hooks) rather than mid-conversation handoffs.

2. **Reviewer subagents are the highest-leverage routing target.** They run on every task (3× per task in strict mode, 1× in batched mode), the prompt is largely template, and the output is short ("approved" / "issues: ..."). 27 tasks × 2 reviewers × ~$0.50 each = ~$27 directly recoverable.

3. **Background subagent dispatches are routing-friendly.** Both /rpi background agents this session ran in parallel with no shared state. This pattern is ideal for OL routing because there's no live conversation to keep coherent — just dispatch, wait, collect.

4. **Don't route the orchestrator itself.** Conversation steering and tool dispatching needs the long-context judgment of cloud models. Route the *workers*, not the *foreman*.

5. **Knowledge work splits cleanly.** Initial extraction (write a learning) → cloud. Forging into the knowledge base, deduping, scoring → local (it's mostly text classification).

## Cost projection if routed

| Routing target | Session cost | Projected with OL | Savings |
|---|---:|---:|---:|
| Mechanical implementers (10 of 28 tasks) | ~$45 | ~$1 (OL inference) | ~$44 |
| Reviewer subagents (4-6 of them this session) | ~$15 | ~$0.50 | ~$14.50 |
| Knowledge forge / extraction | ~$8 | ~$0.30 | ~$7.70 |
| Status reports / formatting | ~$5 | $0 (no LLM) | ~$5 |
| **Subtotal routed** | **~$73** | **~$2** | **~$71** |
| Stays on cloud (judgment + orchestration) | ~$194 | ~$194 | $0 |
| **TOTAL** | **~$267** | **~$196** | **~$71 (27%)** |

## Anti-patterns to avoid

- **Routing the conversation orchestrator to local.** It needs to make routing decisions, which is itself judgment work.
- **Routing without testing equivalence first.** Pick 3 representative subagent prompts, run on cloud and on OL, diff outputs. If OL diverges meaningfully, that subagent type stays on cloud.
- **Hard-coding model choices in skills.** Use a router (hook or middleware) so you can change routing policy without editing every skill.
- **Routing security-relevant decisions to local.** Hard-block enforcement (governance.ts), Director gate validation, code-review for security-sensitive paths — keep cloud.

## Source

Direct observation of this session: 350 turns, $266.61 cost, classified by pattern.
Transcript: `~/.claude/projects/C--Users-kas41/8c687aae-...jsonl`.
