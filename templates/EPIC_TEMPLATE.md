# EPIC — [Area: Title]

**bd:** `bd create "<area>: <title>" --type epic -p P0..P4 -l <area-label>`
**ID:** `<epic-id>` · **Priority:** P0..P4 · **Label:** `<area>` · **Date:** YYYY-MM-DD

> One sentence: what capability or hardening this epic delivers, and why now.

---

## Goal
*The outcome in 1–3 sentences. What is true when this epic closes that is not true today?*

## Why (evidence)
*Tie to concrete signal — audit finding, file:line, metric, recurring decision-log pattern.*

## Acceptance criteria
*The `--acceptance` string. Observable, testable conditions for closing the epic.*
- [ ] …
- [ ] …

## Child beads
*Dependency-ordered. One bead = one artifact + its tests. Create each with `--parent <epic-id>`.*

| # | Bead (title) | Priority | Depends on |
|---|--------------|----------|------------|
| 1 ★ | … | P1 | — |
| 2 | … | P2 | 1 |

*★ = highest-ROI first step (unblocks the rest, lowest risk).*

## Out of scope
- …

## Links
- Roadmap: `docs/research/<TOPIC>_ROADMAP.md`
- PDR (if design-heavy): `08_PDRS/<feature>.md`
- Structure / where it lives: `CHROMATIC_TREES.md`

---
*Create beads → `bd dolt commit` → `bd dolt push`. Each bead ships as its own worktree → PR → CI-green → squash-merge.*
