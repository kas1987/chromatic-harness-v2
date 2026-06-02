# BEAD — [Title]

**bd:** `bd create "<title>" --type task -p P2 --parent <epic-id> -l <area-label>`
**ID:** `<bead-id>` · **Parent epic:** `<epic-id>` · **Priority:** P0..P4 · **Date:** YYYY-MM-DD

> One sentence: the single artifact this bead produces.

---

## Scope (one artifact)
*Exactly one deliverable + its tests. If you need two artifacts, that's two beads.*

## Definition of done
- [ ] Artifact exists at `<path>`
- [ ] Unit tests green (`pytest tests/<file>`)
- [ ] `ruff format` + `ruff check` clean (if code)
- [ ] Integration proved live (not just unit-tested) — name the runtime path
- [ ] PR merged, `bd close <bead-id>`

## Context / pointers
*Files to read first, related beads, the contract it conforms to.*
- Reads: `<path>`
- Schema/contract: `01_PROTOCOLS/<...>`
- Structure map: `CHROMATIC_TREES.md`

## Notes
*Gotchas, prior art, what NOT to do.*

---
*One bead = one artifact + tests. Ship via worktree → PR → full gate → squash-merge.*
