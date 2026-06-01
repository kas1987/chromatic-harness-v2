---
name: 2026-05-19-nightly-extract
type: anti-pattern
confidence: 0.50
source_learnings: [2026-05-19-nightly-extract]
description: Nightly Extract — 2026-05-19
tags: []
---

# Nightly Extract — 2026-05-19

**Commits processed:** 2 (08d0fe4, 64777ee)
**Meaningful signals found:** 2
**Skipped:** 64777ee (previous nightly extract — boilerplate only)

---

## Signal 1: TODO Debt Reaches 14 — One Away From Triage Trigger

**What:** Daily fitness snapshot (08d0fe4) shows `todo_files` increased from 13 (2026-05-18) to 14 (2026-05-19). All other metrics unchanged: 2 skills, 0 rated ≥3, 0 recent verdicts.

**Why:** The prior extract (2026-05-18) established a trigger threshold: "If `todo_files` exceeds 15 in a snapshot, treat as a trigger for a dedicated TODO-triage session." We are now at 14 — one increment away. The trajectory since 2026-05-16 is: 10 → 13 → 13 → 14, averaging roughly +1/day. At this rate the threshold is hit tomorrow.

**Reuse signal:** Next fitness snapshot showing `todo_files >= 15` should immediately spawn a TODO-triage session. The trigger condition is imminent. Known anchor TODO: `whisper-flow-mcp/src/tools/trigger_dictation.ts:54` (confidence hardcoded to 1.0, flagged by drift scan 36123da).

**Source:** 08d0fe4

---

## Signal 2: Skill Rating Gap Persists — Now 13+ Days Unresolved

**What:** Both SKILL.md files (`weekly-skills-reflection`, `worktree-tooling-sweep`) remain below rating 3. `mvs_pct` is 0. This has been the continuous state since at least 2026-05-06, now confirmed through 2026-05-18 (13 days).

**Why:** The skill-improvement loop requires Examples + Troubleshooting sections in each SKILL.md. No agent or human has acted on this despite repeated flagging in prior extracts (2026-05-17, 2026-05-18). The loop is not self-healing — it requires a deliberate one-time authoring pass.

**Reuse signal:** This is the single highest-leverage maintenance action available. Adding Examples + Troubleshooting to both SKILL.md files would move both ratings to ≥3 and shift `mvs_pct` from 0 in the next fitness evaluation. Also blocked: `.agents/skills/` directory (missing), `.claude/skills-schema.md` (missing), `docs/development/WORKTREES.md` (missing) — referenced by the SKILL.md files but never scaffolded.

**Source:** 08d0fe4 (via sustained fitness flatline)

---

## Files with Most Lines Changed Today

| File | Lines Changed | Commit |
|------|--------------|--------|
| `.agents/learnings/2026-05-18-nightly-extract.md` | +77 | 64777ee |
| `.agents/learnings/index.jsonl` | +1 | 64777ee |
| `.agents/evolve/fitness-history.jsonl` | +1 | 08d0fe4 |
| `.agents/evolve/fitness-latest.json` | +1 / -1 | 08d0fe4 |
| `.agents/evolve/fitness-snapshot-2026-05-18.json` | +1 | 08d0fe4 |

