# PDR: Claude Workflow Token Governance & Context Runaway Controls

## 0. Document Metadata

| Field | Value |
|---|---|
| PDR Name | Claude Workflow Token Governance & Context Runaway Controls |
| Project | Chromatic Harness / Claude Code Workflow Layer |
| Version | 0.1.0 |
| Status | Draft for Implementation |
| Owner | Human Operator |
| Primary Systems | Claude Code, `.claude/workflows`, Chromatic Harness governance |
| Incident Trigger | ~1.3M token burn during workflow deployment/audit session |
| Date | 2026-05-28 |

---

## 1. Executive Summary

Claude did not burn ~1.3M tokens because it wrote small workflow files. The burn was caused by an ungated audit pattern: broad transcript scanning, repeated skill reads, giant tool outputs, and workflow-chain designs that pass full prior context into later subagents.

This PDR defines a bounded workflow governance layer to prevent future token runaway. It introduces hard budgets, transcript access rules, compressed handoff packets, workflow mode separation, cost gates before subagent calls, and acceptance tests for Claude workflow behavior.

## 2. Problem Statement

A Claude Code session performed a broad skill/transcript audit and then deployed several user-global workflow files. The workflows themselves were tiny, but the surrounding audit and workflow design created extreme token exposure.

### Observed failure pattern

| Area | Failure |
|---|---|
| Transcript access | Scanned or sampled many `~/.claude/projects/**/*.jsonl` files |
| Skill access | Re-read many `SKILL.md` files and validation outputs |
| Tool output | Returned large tables and script output into context |
| Workflow chaining | Passed entire phase outputs forward rather than compressed handoffs |
| Budgeting | No hard token/tool/file caps visible at workflow boundary |
| Stop conditions | No clear halt rule for broad discovery or runaway audit |

## 3. Goals

1. Prevent unbounded transcript mining during normal workflow runs.
2. Prevent workflow chains from compounding context through full-output forwarding.
3. Add explicit token, file-read, tool-call, and output budgets.
4. Split lite, normal, and deep workflows by risk and budget.
5. Require cost gates before each subagent or phase call.
6. Make token governance easy for Claude, Codex, ChatGPT, and local agents to follow.
7. Preserve useful audit capability without allowing accidental million-token sessions.

## 4. Non-Goals

This PDR does not attempt to:

- remove Claude Code or Claude workflows;
- ban transcript analysis entirely;
- rewrite the full Chromatic Harness router;
- optimize model pricing directly;
- solve every MCP or skill descriptor token issue in one pass.

## 5. Scope

### In scope

- `C:\Users\kas41\.claude\workflows\`
- Claude workflow governance docs
- workflow JS patch patterns
- token budget headers
- compressed handoff format
- audit-lite vs audit-deep separation
- cost incident template
- acceptance tests and validation checklist

### Out of scope

- GitHub Actions CI workflows unless they call Claude workflows
- unrelated repo structure cleanup
- MCP server redesign
- private transcript deletion policies
- model-provider billing disputes

## 6. Incident Root Cause Analysis

### Root cause 1: Ungated transcript and skill audit

The session inspected large local history and skill corpora without first constraining the audit scope. With roughly 1,942 JSONL files and about 370 MB of transcript history, even a small fraction returned into the thread can plausibly burn around one million tokens.

### Root cause 2: Full-output workflow chaining

The new workflow style chains multiple phases:

```text
discovery -> plan -> crank -> vibe -> release
```

If each phase receives the full output of all previous phases, token cost compounds. This turns an orchestration script into a context amplifier.

### Root cause 3: No budget gates before subagent dispatch

Each `agent()` call behaves like a new high-context subagent. Without phase-level budget checks, a single workflow can invoke multiple expensive agents sequentially or in parallel.

### Root cause 4: Tool output pollution

Large shell outputs, validation tables, and full file reads were allowed back into the conversation. This converts local filesystem inspection into permanent context load.

## 7. Proposed Solution

Implement a workflow governance layer made of five controls:

1. `00_WORKFLOW_GOVERNANCE.md` as the source-of-truth rules file.
2. Compressed handoff packets between workflow phases.
3. Budget constants in every workflow.
4. Workflow mode separation: lite, normal, deep.
5. Cost gate checks before every subagent call.

## 8. Required Artifacts

| Artifact | Path | Purpose |
|---|---|---|
| Workflow governance doc | `.claude/workflows/00_WORKFLOW_GOVERNANCE.md` | Human + agent-readable rules |
| Budget contract | `.claude/workflows/WORKFLOW_BUDGET_CONTRACT.md` | Standard token/tool/file caps |
| Handoff schema | `.claude/workflows/HANDOFF_PACKET_SCHEMA.md` | Prevents full context chaining |
| Cost incident template | `.claude/workflows/COST_INCIDENT_TEMPLATE.md` | Repeatable incident reviews |
| Workflow patch spec | `workflow_patches/ship_js_patch_spec.md` | How to update `ship.js` |
| Agent handoffs | `handoffs/*.md` | Implementation, audit, and QA work packets |
| Acceptance checklist | `tests/ACCEPTANCE_CHECKLIST.md` | Done criteria |

## 9. Workflow Budget Policy

### Default budget classes

| Workflow Class | Max Context Read | Max Tool Calls | Max Files Read | Max Output Per Phase | Transcript Access |
|---|---:|---:|---:|---:|---|
| Lite | 25k tokens | 6 | 4 | 1,000 tokens | Forbidden |
| Normal | 75k tokens | 12 | 10 | 1,500 tokens | Forbidden by default |
| Audit Lite | 40k tokens | 8 | 6 | 1,500 tokens | Indexed summaries only |
| Deep Audit | Explicit approval | Explicit approval | Explicit approval | 2,000 tokens | Max scoped sample unless approved |
| Swarm / Ship Deep | Explicit approval | Explicit approval | Explicit approval | 2,000 tokens | Forbidden unless part of approved audit |

### Stop conditions

A workflow must halt if:

- it attempts to read all transcript files;
- it repeats a broad glob search without narrowing scope;
- it reads the same file more than twice without a state change;
- it exceeds budget;
- it cannot estimate token risk;
- it needs destructive or external actions;
- it tries to pass full prior outputs to the next phase.

## 10. Transcript Access Policy

Default rule:

```text
Normal workflows may not read `~/.claude/projects/**/*.jsonl`.
```

Allowed alternatives:

1. Read precomputed summary indexes.
2. Read explicit file paths provided by the operator.
3. Sample no more than 3 transcript files in audit-lite mode.
4. Require explicit `DEEP_AUDIT_APPROVED=true` for broader mining.

## 11. Context Passing Policy

### Forbidden pattern

```js
const plan = await agent(`/plan ${discovery}`);
const crank = await agent(`/crank ${discovery}\n${plan}`);
const release = await agent(`/release ${discovery}\n${plan}\n${crank}`);
```

### Required pattern

```js
const discoveryPacket = compressToHandoff(discovery);
const plan = await agent(`/plan`, { context: discoveryPacket });
const planPacket = compressToHandoff(plan);
const crank = await agent(`/crank`, { context: planPacket });
```

### Required handoff packet

```json
{
  "objective": "",
  "decision": "",
  "evidence_refs": [],
  "files_touched": [],
  "risks": [],
  "blockers": [],
  "next_action": "",
  "confidence": 0,
  "budget_used": {
    "tool_calls": 0,
    "files_read": 0,
    "approx_tokens": 0
  }
}
```

## 12. Implementation Plan

### Phase 1: Containment

- Add `00_WORKFLOW_GOVERNANCE.md`.
- Add `WORKFLOW_BUDGET_CONTRACT.md`.
- Add transcript access ban by default.
- Mark current `ship.js` as unsafe until patched.

### Phase 2: Workflow patching

- Modify `ship.js` to use compressed handoff packets.
- Add budget constants.
- Add pre-agent cost gates.
- Add phase output caps.
- Add halt-on-broad-scan rules.

### Phase 3: Workflow separation

Create or rename workflows:

| Workflow | Purpose |
|---|---|
| `ship-lite.js` | Small feature shipment with low context budget |
| `ship.js` | Normal bounded feature workflow |
| `ship-deep.js` | Explicitly approved high-context swarm delivery |
| `audit-lite.js` | File/state audit without transcript mining |
| `audit-deep.js` | Explicitly approved transcript/skill mining |
| `cost-audit.js` | Token/tool incident investigation using summaries first |

### Phase 4: Validation

- Run static checks on workflow files.
- Confirm every `agent()` call has a budget gate.
- Confirm no workflow passes raw full phase output forward.
- Confirm transcript glob access is blocked or guarded.
- Confirm acceptance checklist passes.

## 13. Acceptance Criteria

This PDR is implemented when:

- [ ] `00_WORKFLOW_GOVERNANCE.md` exists in the Claude workflow directory.
- [ ] Every workflow has a budget header.
- [ ] Every `agent()` call has a cost gate.
- [ ] `ship.js` uses compressed handoffs only.
- [ ] Transcript glob access is forbidden by default.
- [ ] Deep audit requires explicit approval.
- [ ] Phase output caps are defined.
- [ ] Cost incident template exists.
- [ ] Test checklist passes.
- [ ] A future `ship` run can be bounded to a known budget class.

## 14. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Claude ignores governance doc | High | Add inline workflow guards, not just docs |
| Budget estimates are approximate | Medium | Use conservative caps and hard file/tool limits |
| Deep audit still needed sometimes | Medium | Require explicit approval and sample limits |
| Workflow patch breaks existing commands | Medium | Add `ship-lite.js` first, then patch normal `ship.js` |
| User-global workflows drift from repo governance | Medium | Mirror workflow specs into version-controlled repo docs |

## 15. Recommended Agent Routing

| Task | Agent / Model | Why |
|---|---|---|
| Patch JS workflows | Codex / code-specialized agent | Best for repo edits and tests |
| Review governance docs | Claude / ChatGPT | Strong synthesis and policy review |
| Validate cost controls | Auditor agent | Needs adversarial review |
| Build transcript summary index | Local LLM or cheap model | Repeated classification/summarization |
| Final merge review | Human + auditor | Prevents accidental governance bypass |

## 16. Best Next Action

Create `00_WORKFLOW_GOVERNANCE.md` and patch `ship.js` so every workflow phase receives a compressed handoff packet instead of full previous output.
