---
name: 2026-05-21-nightly-extract
type: anti-pattern
confidence: 0.50
source_learnings: [2026-05-21-nightly-extract]
description: Nightly Extract — 2026-05-21
tags: []
---

# Nightly Extract — 2026-05-21

**Commits processed:** 2 (829acf5, b91a591)
**Meaningful signals found:** 2
**Skipped:** b91a591 (previous nightly extract — boilerplate only); 829acf5 (fitness snapshot — metrics update only, no skill/hook/settings changes)

---

## Signal 1: TODO Debt Now Exceeds Trigger Threshold (todo_files = 16)

**What:** Daily fitness snapshot (829acf5) records `todo_files = 16` as of 2026-05-20, up from 15 the prior day. Trajectory since 2026-05-16: 10 → 13 → 13 → 14 → 15 → 16. The documented trigger threshold (set in the 2026-05-19 extract) was 15. That threshold has now been exceeded for two consecutive days.

**Why:** The triage trigger was defined precisely to prevent silent drift. Known anchor confirmed by drift scan: `whisper-flow-mcp/src/tools/trigger_dictation.ts:54` (confidence hardcoded to 1.0). No triage session has been spawned despite the trigger being met as of 2026-05-20.

**Reuse signal:** Spawn a dedicated TODO-triage session. Start at `whisper-flow-mcp/src/tools/trigger_dictation.ts:54`. Sweep all TODO-tagged files; for each decide: fix now, defer with date, or delete. Goal: bring `todo_files` below 15.

**Source:** 829acf5

---

## Signal 2: Skill Rating Gap — Now 15+ Days Unresolved, Zero Progress

**What:** Both SKILL.md files (`weekly-skills-reflection`, `worktree-tooling-sweep`) remain below rating 3. `mvs_pct` = 0. Continuous flatline since at least 2026-05-06, confirmed through 2026-05-20 (15 days). Flagged in extracts for 2026-05-17, 2026-05-18, 2026-05-19, and 2026-05-20 with no action taken.

**Why:** The skill-improvement loop requires Examples + Troubleshooting sections in both SKILL.md files. These remain absent. Additionally, `.agents/skills/`, `.claude/skills-schema.md`, and `docs/development/WORKTREES.md` — all referenced by the SKILL.md files — have never been scaffolded.

**Reuse signal:** One authoring pass on both SKILL.md files (add Examples + Troubleshooting) moves both to ≥3 and shifts `mvs_pct` from 0. This remains the single highest-leverage maintenance action available. Per the prior extract's escalation note, this should now be treated as a blocking issue (threshold date: 2026-05-22 is tomorrow).

**Source:** 829acf5 (via sustained fitness flatline)

---

## Files with Most Lines Changed Today

| File | Lines Changed | Commit |
|------|--------------|--------|
| `.agents/learnings/2026-05-20-nightly-extract.md` | +41 | b91a591 |
| `.agents/learnings/index.jsonl` | +1 | b91a591 |
| `.agents/evolve/fitness-snapshot-2026-05-20.json` | +1 | 829acf5 |
| `.agents/evolve/fitness-history.jsonl` | +1 | 829acf5 |
| `.agents/evolve/fitness-latest.json` | +1 / -1 | 829acf5 |

