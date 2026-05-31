---
name: 2026-05-18-nightly-extract
type: anti-pattern
confidence: 0.50
source_learnings: [2026-05-18-nightly-extract]
description: Nightly Extract — 2026-05-18
tags: []
---

# Nightly Extract — 2026-05-18

**Commits processed:** 3 (a986f18, 36123da, 367c987)
**Meaningful signals found:** 5
**Skipped:** 367c987 (previous nightly extract — boilerplate only)

---

## Signal 1: Weekly Drift Scan Pattern Established

**What:** `chore: weekly drift scan` (36123da) ran a comprehensive static analysis across the repo, producing `.agents/evolve/drift-findings-2026-05-17.jsonl` and a human-readable report. Categories: TODOs, large files (>300 lines), broken links, hook dead refs, skill gaps.

**Why:** Provides a structured, repeatable audit cadence to catch accumulating debt before it becomes invisible. Drift scan runs weekly; nightly extract runs daily — two different granularities of health monitoring.

**Reuse signal:** The drift scan output format (typed JSONL with file/line/detail) is a stable schema other tools can consume. Any agent that wants to triage or prioritize remediation work should read `.agents/evolve/drift-findings-latest.jsonl`.

**Source:** 36123da

---

## Signal 2: TODO Debt Growing — todo_files 10 → 13

**What:** Daily fitness snapshot (a986f18) shows `todo_files` increased from 10 (2026-05-16) to 13 (2026-05-17). All other metrics unchanged: 2 skills, 0 rated ≥3, 0 recent verdicts.

**Why:** Three new files contain TODO markers in one day. Combined with the drift scan finding 1 explicit TODO (`whisper-flow-mcp/src/tools/trigger_dictation.ts:54` — confidence hardcoded to 1.0), the TODO backlog is expanding without corresponding resolution.

**Reuse signal:** If `todo_files` exceeds 15 in a snapshot, treat as a trigger for a dedicated TODO-triage session. Current trajectory: +1.5/day over the past 2 days.

**Source:** a986f18

---

## Signal 3: Hook Dead Refs — model-router.sh Partially Wired

**What:** Drift scan identified 4 dead refs across 3 hooks. Most significant: `hooks/model-router.sh` references `~/.claude/.agents/router/` (log dir, line 21) and `~/.claude/config/router-patterns.json` (pattern config, line 48) — neither exists.

**Why:** The model-router hook is registered and fires on Agent dispatches (per CLAUDE.md), but its logging and pattern-matching paths are missing. The hook notes it "never blocks — only advises," so this silently degrades routing quality without failing visibly.

**Reuse signal:** Before relying on OL-layer routing decisions, verify `~/.claude/.agents/router/log.jsonl` is being written. If absent, the hook is firing but producing no output. Also: `hooks/pre-push.sh` references `~/.claude/bin/start-session.sh` (help text only, low priority).

**Source:** 36123da

---

## Signal 4: Both Skills Persistently Below Rating 3 — Missing Sections

**What:** Drift scan confirmed both SKILL.md files (`weekly-skills-reflection`, `worktree-tooling-sweep`) lack `Examples` and `Troubleshooting` sections. Fitness snapshot: 0 of 2 skills rated ≥3. This has been the state since at least 2026-05-06 (per prior extracts).

**Why:** Skills without Examples and Troubleshooting sections cannot be rated ≥3 by the fitness evaluator. The gap has persisted for 12+ days without remediation, indicating the skill-improvement loop is not triggering automatically.

**Reuse signal:** A one-time pass adding Examples + Troubleshooting to both SKILL.md files would move both ratings to ≥3 and shift `mvs_pct` from 0. This is the single highest-leverage action available given current fitness data.

**Source:** 36123da, a986f18

---

## Signal 5: Broken Links in SKILL.md Files — Missing Schema and Index

**What:** `scheduled-tasks/weekly-skills-reflection/SKILL.md` references `.claude/skills-schema.md`, `.agents/skills/reflections/`, and `.agents/skills/_index.md` — none exist. `scheduled-tasks/worktree-tooling-sweep/SKILL.md` references `docs/development/WORKTREES.md` — also missing.

**Why:** These are structural references that skills rely on for guidance and output routing. Their absence means the skills, when executed, cannot persist reflections or validate against schema definitions — output goes nowhere.

**Reuse signal:** Before running either scheduled skill, create the missing paths or update the SKILL.md references to point at existing infrastructure. The `.agents/skills/` directory pattern may have been planned but never scaffolded.

**Source:** 36123da

---

## Files with Most Lines Changed Today

| File | Lines Changed | Commit |
|------|--------------|--------|
| `.agents/evolve/drift-report-2026-05-17.md` | +60 | 36123da |
| `.agents/evolve/drift-findings-2026-05-17.jsonl` | +18 | 36123da |
| `.agents/evolve/drift-findings-latest.jsonl` | +18 | 36123da |
| `.agents/evolve/fitness-latest.json` | +1 / -12 | a986f18 |
| `.agents/evolve/fitness-snapshot-2026-05-17.json` | +1 | a986f18 |

