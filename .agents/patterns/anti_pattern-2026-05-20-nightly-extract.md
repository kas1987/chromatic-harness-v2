---
name: 2026-05-20-nightly-extract
type: anti-pattern
confidence: 0.50
source_learnings: [2026-05-20-nightly-extract]
description: Nightly Extract — 2026-05-20
tags: []
---

# Nightly Extract — 2026-05-20

**Commits processed:** 2 (e3599c9, 543dd02)
**Meaningful signals found:** 2
**Skipped:** 543dd02 (previous nightly extract — boilerplate only)

---

## Signal 1: TODO Debt Hits Triage Trigger Threshold (todo_files = 15)

**What:** Daily fitness snapshot (e3599c9) records `todo_files = 15` as of 2026-05-19, up from 14 the previous day. Trajectory since 2026-05-16: 10 → 13 → 13 → 14 → 15. The prior extract (2026-05-19) explicitly documented: "If `todo_files` exceeds 15 in a snapshot, treat as a trigger for a dedicated TODO-triage session." That threshold is now met.

**Why:** Unchecked TODO accumulation degrades signal quality in the codebase; the triage trigger was set precisely to prevent silent drift. Known anchor: `whisper-flow-mcp/src/tools/trigger_dictation.ts:54` (confidence hardcoded to 1.0, flagged by drift scan 36123da).

**Reuse signal:** A dedicated TODO-triage session should be spawned. Start with `whisper-flow-mcp/src/tools/trigger_dictation.ts:54` as the first confirmed target. Sweep remaining TODO files to decide: fix now, defer with date, or delete.

**Source:** e3599c9

---

## Signal 2: Skill Rating Gap — Now 14+ Days Unresolved, Still Zero Progress

**What:** Both SKILL.md files (`weekly-skills-reflection`, `worktree-tooling-sweep`) remain below rating 3. `mvs_pct` is 0. Continuous state since at least 2026-05-06, confirmed through 2026-05-19 (14 days). No agent or human action taken despite flagging in extracts for 2026-05-17, 2026-05-18, and 2026-05-19.

**Why:** The skill-improvement loop requires Examples + Troubleshooting sections. These are missing from both SKILL.md files. The loop is not self-healing. Also still missing: `.agents/skills/` directory, `.claude/skills-schema.md`, `docs/development/WORKTREES.md` — all referenced by the SKILL.md files but never scaffolded.

**Reuse signal:** One authoring pass on both SKILL.md files (adding Examples + Troubleshooting) would move both ratings to ≥3 and shift `mvs_pct` from 0. This remains the single highest-leverage maintenance action available. Consider escalating to a blocking issue if still unresolved at 2026-05-22.

**Source:** e3599c9 (via sustained fitness flatline)

---

## Files with Most Lines Changed Today

| File | Lines Changed | Commit |
|------|--------------|--------|
| `.agents/learnings/2026-05-19-nightly-extract.md` | +41 | 543dd02 |
| `.agents/learnings/index.jsonl` | +1 | 543dd02 |
| `.agents/evolve/fitness-history.jsonl` | +1 | e3599c9 |
| `.agents/evolve/fitness-latest.json` | +1 / -1 | e3599c9 |
| `.agents/evolve/fitness-snapshot-2026-05-19.json` | +1 | e3599c9 |

