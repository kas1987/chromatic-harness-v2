# Rules inventory (Chromatic Harness v2)

Single map of **where rules live** and **which layer wins** when they conflict.

## Priority (highest first)

| Priority | Source | Scope |
|----------|--------|--------|
| 1 | User chat instruction | This turn only |
| 2 | **Project** `.cursor/rules/*.mdc` (`alwaysApply: true`) | This repo in Cursor |
| 3 | `AGENT_OPERATIONS.md` + `docs/governance/*` | All harness agents |
| 4 | `AGENTS.md` / `CLAUDE.md` (thin wrappers) | Per-tool entry |
| 5 | **Global** `~/.cursor/rules/*.mdc` | All Cursor workspaces |
| 6 | Cursor **User Rules** (Settings → Rules) | All sessions — paste from [cursor/USER_RULES_SNIPPET.md](cursor/USER_RULES_SNIPPET.md) |
| 7 | Default model behavior | Lowest |

**Git:** For `chromatic-harness-v2`, project `git-autonomy.mdc` + `GIT_AUTONOMY_POLICY.md` override generic "commit only when asked" user rules.

---

## Project rules (`.cursor/rules/`)

| File | alwaysApply | Purpose |
|------|-------------|---------|
| [context-hygiene.mdc](../.cursor/rules/context-hygiene.mdc) | yes | Lean MCP; session boot; no token burn |
| [git-autonomy.mdc](../.cursor/rules/git-autonomy.mdc) | yes | Tiered commit/push/merge in this repo |
| [karpathy-guidelines.mdc](../.cursor/rules/karpathy-guidelines.mdc) | yes | Surgical diffs; success criteria; pairs with roach-pi `discipline.ts` |

---

## Global rules (`~/.cursor/rules/`)

| File | alwaysApply | Purpose |
|------|-------------|---------|
| [chromatic-harness.mdc](file:///C:/Users/kas41/.cursor/rules/chromatic-harness.mdc) | manual* | Federation roots, model tiers, MCP, quality gates |
| [git-autonomy-global.mdc](file:///C:/Users/kas41/.cursor/rules/git-autonomy-global.mdc) | yes | Tiered git across harness repos |

\*Enable "Always apply" in Cursor rule picker if you want federation rules every session.

---

## Agent instruction files (repo root)

| File | Audience | Content |
|------|----------|---------|
| [AGENT_OPERATIONS.md](../AGENT_OPERATIONS.md) | All agents | Session boot, GO, git tiers, MCP, session end |
| [AGENTS.md](../AGENTS.md) | Codex/Cursor/etc. | Wrapper → AGENT_OPERATIONS |
| [CLAUDE.md](../CLAUDE.md) | Claude Code | Wrapper + minimal beads block |
| [CLAUDE.md](../CLAUDE.md) (parent) | — | N/A |

Home `~/AGENTS.md` is a **generic beads template**; prefer repo `AGENTS.md` when inside harness-v2.

---

## Governance docs (policy source of truth)

| Doc | Topic |
|-----|--------|
| [docs/governance/GIT_AUTONOMY_POLICY.md](governance/GIT_AUTONOMY_POLICY.md) | Commit/push/PR/merge tiers |
| [docs/governance/CONFIDENCE_GATE.md](governance/CONFIDENCE_GATE.md) | Score bands + self-heal |
| [docs/governance/WORKFLOW_BUDGET_CONTRACT.md](governance/WORKFLOW_BUDGET_CONTRACT.md) | Lite workflow token caps |
| [docs/governance/PRE_SESSION_CONTEXT_POLICY.md](governance/PRE_SESSION_CONTEXT_POLICY.md) | Context tiers P0–P4 |
| [docs/workflows/PERMISSION_GATE.md](workflows/PERMISSION_GATE.md) | Action permissions |
| [docs/workflows/GO_MODES.md](workflows/GO_MODES.md) | GO / self-heal |
| [docs/AGENT_ANTIPATTERNS.md](AGENT_ANTIPATTERNS.md) | Do-not-trust list |
| [docs/governance/KARPATHY_DISCIPLINE.md](governance/KARPATHY_DISCIPLINE.md) | Karpathy 4-pillar canon (implementation discipline) |

---

## Runtime enforcement (code)

| Component | Enforces |
|-----------|----------|
| `02_RUNTIME/workflows/git_policy.py` | Confidence thresholds |
| `02_RUNTIME/workflows/permission.py` | GIT_* and PUSH_MERGE_DEPLOY |
| `scripts/workflow_git.py` | plan → ship pipeline |
| `scripts/validate_instruction_governance.py` | Thin wrappers |
| `scripts/validate_governance_stack.py` | CI gate bundle |
| `scripts/check_agent_operations.py` | Required docs + links |
| `roach-pi/.../discipline.ts` | Karpathy 4-pillar injection on plan-worker / worker |
| `02_RUNTIME/magnets/discipline_magnet.py` | Karpathy telemetry scoring |
| `scripts/validate_karpathy_discipline.py` | CI wiring gate |

---

## Cursor User Rules (Settings UI)

Cursor stores **User Rules** in the product settings (not always a repo file). Sync text from:

**[docs/cursor/USER_RULES_SNIPPET.md](cursor/USER_RULES_SNIPPET.md)**

Replace legacy blocks that say "only commit when requested" / "never push unless asked" with the tiered harness language there.

---

## Review checklist (quarterly)

- [ ] `python scripts/validate_governance_stack.py` passes
- [ ] `python scripts/context_trim_audit.py` risk not red
- [ ] No duplicate Session Completion blocks in AGENTS + CLAUDE + AGENT_OPERATIONS
- [ ] Global `git-autonomy-global.mdc` present
- [ ] User Rules in Cursor Settings match `USER_RULES_SNIPPET.md`
- [ ] Lite workflows synced: `scripts/sync_claude_workflows.ps1`
