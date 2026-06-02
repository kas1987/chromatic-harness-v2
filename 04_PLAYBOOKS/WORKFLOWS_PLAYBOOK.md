# Workflows Playbook — Operate the Harness as Claude Workflows

> **The harness operates as a set of token-bounded Claude Code workflows.** Each lifecycle
> step is a workflow in [`.claude/workflows/`](../.claude/workflows/) using the standard
> `export const meta = { name, description, phases }` + `phase()` / `agent()` / `bash()` /
> `parallel()` API, with per-phase budget guards from `_budget.js`.
>
> **Authority:** structure & file map → [`CHROMATIC_TREES.md`](../CHROMATIC_TREES.md) ·
> operational checklist → [`AGENT_OPERATIONS.md`](../AGENT_OPERATIONS.md) ·
> budget contract → [`docs/governance/WORKFLOW_BUDGET_CONTRACT.md`](../docs/governance/WORKFLOW_BUDGET_CONTRACT.md).

---

## The lifecycle = workflows

The full path from idea to merged change is a chain of bounded workflows. Run them
one at a time; each emits a compressed handoff packet, not a full transcript.

| Step | Workflow | Command | What it does | Est. tokens |
|------|----------|---------|--------------|-------------|
| **Audit** | `audit.js` | `/audit [slices]` | Bounded parallel read-only Explore fan-out → findings | ~60–90k |
| **Plan** | `plan.js` | `/plan <goal\|roadmap>` | Decompose → ONE epic + child beads (templates + bd) | ~40–60k |
| **Ship (plan-only)** | `ship.js` | `/ship <feature>` | Discovery + plan → beads handoff (no crank) | ~50–150k |
| **Execute** | `go.js` | `/go [mode]` | `workflow_go` score → self-heal → one bead → verify | ~30–80k |
| **Close one** | `close-issue.js` | `/close-issue <id>` | Implement one bead → pytest → push | ~30–80k |
| **Hotfix** | `hotfix.js` | `/hotfix <bug>` | bug-hunt → minimal patch → pytest → push | ~40–100k |
| **QA** | `qa.js` | `/qa` | `pytest` + `ruff` summary only | ~10–30k |

`audit.js` and `plan.js` are the **planning** workflows (added to close the lifecycle gap —
previously only the execution side existed). They make the audit→roadmap→epic→beads flow
reproducible instead of ad-hoc.

## Rules (token discipline)

1. Workflows pass **bead IDs + file paths + compressed handoff packets** — never full prior transcripts (`_budget.js` enforces `transcriptAccess: 'forbidden'`).
2. Each phase calls `assertBudgetAllows({...})` before doing work; over-budget phases throw.
3. **Bounded fan-out only.** `audit.js` uses a fixed slice list. **Never** `/crank`, `/swarm`, or `/council` from a lite workflow — those are unbounded ([AGENT_ANTIPATTERNS](../docs/AGENT_ANTIPATTERNS.md)).
4. `*.HEAVY.js.bak` are archived (they caused ~1.3M-token burns). **Never** restore without explicit human approval.
5. Read-only workflows (`/audit`) must not write files; planning workflows (`/plan`) create beads but no code.

## Authoring a new workflow

1. Copy the shape of `go.js`: `import { BUDGET, assertBudgetAllows, compressToHandoff } from './_budget.js'`, then `export const meta = {...}`, then `phase()` blocks.
2. Budget-guard **every** phase. Keep the total within the `_budget.js` `normal` class (≤75k context, ≤12 tool calls).
3. Return a small packet (`status`, `next`, compressed summary) — not raw agent output.
4. Add the command to [`.claude/workflows/README.md`](../.claude/workflows/README.md) **and** to the table above.
5. Sync to global: `powershell -File scripts/sync_claude_workflows.ps1`.

## Sync & install

```powershell
powershell -File scripts/sync_claude_workflows.ps1   # project .claude/workflows → ~/.claude/workflows
```

---
*One workflow at a time. Bounded budgets. Bead IDs not transcripts. The lifecycle is the chain: `/audit → /plan → /go → /close-issue` with `/qa` and `/hotfix` as needed.*
