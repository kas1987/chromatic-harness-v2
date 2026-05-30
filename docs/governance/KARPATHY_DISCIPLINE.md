# Karpathy discipline (canonical)

Source: [andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) / Karpathy's LLM coding pitfalls thread.

**Applies to:** Cursor agents, roach-pi `plan-worker` / `worker`, Fusion `DisciplineMagnet`, Harness v2 `discipline_magnet`.

## Four pillars

### 1. Think before coding

- State assumptions explicitly; ask if uncertain.
- If multiple interpretations exist, present them — do not pick silently.
- If a simpler approach exists, say so.
- If unclear, stop and name what is confusing.

### 2. Simplicity first

- Minimum code that solves the problem; nothing speculative.
- No features, abstractions, config knobs, or impossible-case error handling unless asked.
- If the change could be half the size, rewrite it.

### 3. Surgical changes

**Hard gates (no exceptions on implementation agents):**

1. Read before you write.
2. Scope to the request — no "while I'm here" work.
3. Verify, don't assume — grep/read types and callers.
4. Match existing project patterns.

- Remove only orphans your edit created; do not delete unrelated dead code unless asked.
- Every changed line must trace to the user request.

### 4. Goal-driven execution

Transform tasks into verifiable goals:

| Task | Success criteria |
|------|------------------|
| Add validation | Tests for invalid inputs pass |
| Fix bug | Repro test fails then passes |
| Refactor | Tests pass before and after |

Multi-step work:

```text
1. [Step] → verify: [command or check]
2. [Step] → verify: [command or check]
```

Do not claim done without running the stated checks.

## Pre-implementation checklist

- [ ] Assumptions stated or questions asked
- [ ] Success criteria written (concrete, not "works")
- [ ] Files to touch identified; everything else off-limits
- [ ] Files read before edit
- [ ] Simplest approach chosen

## Runtime signals (`discipline_magnet` / `DisciplineMagnet`)

| Signal | Meaning |
|--------|---------|
| `read_paths` | Files read this session before edit |
| `modified_paths` | Files written |
| `expected_paths` | Allowed paths for this task |
| `has_success_criteria` | Agent stated verifiable done |
| `assumptions_stated` | Agent surfaced assumptions or questions |
| `verification_ran` | Stated checks were executed (pytest, lint, etc.) |
| `lines_changed` / `max_lines_hint` | Diff size guard |

## Enforcement map

| Layer | Mechanism |
|-------|-----------|
| Cursor | `.cursor/rules/karpathy-guidelines.mdc` |
| Pi runtime | `discipline.ts` → `augmentAgentWithKarpathy` |
| Harness v2 magnets | `02_RUNTIME/magnets/discipline_magnet.py` |
| Fusion Computer | `fusion_computer/harness/magnets/discipline.py` |
| CI | `scripts/validate_karpathy_discipline.py` |
