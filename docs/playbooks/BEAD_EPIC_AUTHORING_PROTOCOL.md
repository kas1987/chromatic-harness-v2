# Bead & Epic Authoring Protocol

> **Read this before creating any epic or bead.** It encodes the order of operations,
> the `bd`/Dolt lock model, the field formats that are easy to get wrong, and where
> PDRs/plans live. Following it keeps the bead store clean and dispatch-ready.

## 1. The flow (PDR → plan → epic → beads)

Work enters the harness in one direction. Don't skip steps.

```
PDR (the spec)                    →  08_PDRS/PDR_<NAME>.md   (canonical home)
   │                                 docs/pdr/<area>/...      (supporting docs)
   ▼
Plan (decomposition)              →  .agents/plans/YYYY-MM-DD-<slug>.md   (via /plan)
   │
   ▼
Epic + child beads (tracking)     →  bd  (Dolt-backed; the ONLY task tracker)
   │
   ▼
Dispatch / execution              →  bd ready → /crank or /implement
```

- **PDRs** live in `08_PDRS/` (canonical) with area detail under `docs/pdr/<area>/`.
- **Plans** live in `.agents/plans/` — always produced by `/plan`, never hand-waved.
- **Tracking** is **bd only**. Never use TodoWrite / TaskCreate / markdown TODO lists.
- Queue/handoff surfaces: `07_LOGS_AND_AUDIT/review_intake/queue.json` (review-intake),
  `12_HANDOFFS/`, `.agents/handoffs/`. Do **not** use `00_PLANNING/` (PDR zip scaffold only).

## 2. The lock model — why you MUST serialize `bd` writes

`bd` is backed by an **embedded Dolt database with a single-writer lock**. Two `bd`
write commands running at the same time collide and one fails (`exit 1`).

> **DO NOT** remove or disable this lock. It protects the bead store from corruption.
> The cure for contention is **serialization**, not lock removal.

**Rules:**
- Run `bd create` / `bd update` / `bd dep add` / `bd close` **one at a time**, in sequence.
- **Never** fan `bd` writes out in parallel, in background tasks, or via `&`.
- If a `bd` write fails with exit 1/143/255, it's almost always contention or a stray
  background `bd` process — check `Get-Process bd,dolt`, let it drain, retry **serially**.
- Reads (`bd ready`, `bd show`, `bd list`) are safe but can be slow; don't parallelize them either.

These are **Dolt DB locks**, distinct from harness *governance* locks (review-intake PR
branch locks, file-collision lease gates). Governance locks only fire at dispatch/mutation
time and are not active while you author beads — leave them on.

## 3. Field formats that bite (get these right the first time)

| Field | Correct | Common mistake |
|------|---------|----------------|
| `--priority` | **`0`–`4`** or **`P0`–`P4`** | Passing a 0–100 confidence score (`95`, `92`). bd rejects it: *"invalid priority"*. **Map** confidence→P-level (see below). |
| `--type` | `epic`, `task`, `feature`, `chore`, `bug` | Omitting `--type epic` on the parent. |
| `--parent` | the epic id (e.g. `…-1j62`) | Creating children with no parent → orphans. |
| dependency | `bd dep add <issue> <depends-on>` | Reversing the args. `<issue>` becomes blocked by `<depends-on>`. |
| validation | fenced ```` ```validation ```` JSON block in `--description` | Omitting it → `/crank` falls back to weak `files_exist` checks. |

**Confidence (0–100) → bd priority (P0–P4) mapping** (PDR confidence bands):

| Confidence | Band | bd priority |
|---:|---|:--|
| 90–100 | Very High | `P0`/`P1` |
| 75–89 | High | `P1`/`P2` |
| 60–74 | Medium | `P2`/`P3` |
| 40–59 | Low | `P3` |
| 0–39 | Blocked | `P4` |

## 4. Waves = dependencies (not a field)

`bd ready` returns the current wave — every unblocked bead. Form waves with `bd dep add`:
- No blockers → **Wave 1** (shows in `bd ready` immediately).
- Blocked by a Wave-1 bead → **Wave 2** (appears when the blocker closes).
- Only add a dependency if the blocked bead **reads the blocker's output** or **shares a
  file** with it. Logical-ordering-only deps kill parallelism — drop them.

## 5. Every child bead needs a validation block

Embed conformance checks so `/crank` can verify completion mechanically:

````
```validation
{"files_exist": ["scripts/x.py"], "command": "python scripts/x.py --root ."}
```
````

Use only `validation-contract` types: `files_exist`, `content_check`, `command`, `tests`, `lint`.
Prefer `files_exist`/`content_check` (fast, deterministic) over `command`.

## 6. Agent-bead hygiene (the "noise" problem)

Session bootstrap and decision flows materialize `[agent]` beads — e.g.
`[agent] bd ready`, `[agent] Halt mission and escalate`, `[agent] Run new_session_bootstrap.py`.
These accumulate fast (93 found on 2026-06-02, 18 stuck `in_progress`).

**Rules:**
- **Never hand-author `[agent]`-prefixed beads.** They are machine ephemera, not work items.
- They must be **ephemeral** (`bd create --ephemeral`) so TTL compaction reaps them, and
  closed at session end. The janitor is `scripts/hooks/close_stale_agent_beads.py` — if
  `in_progress` `[agent]` beads pile up, that hook isn't running or isn't closing them.
- Keep real work beads and `[agent]` lifecycle beads in separate lanes: filter `[agent]`
  out of `bd ready` reviews, and never let them gain a `--parent` epic.

## 7. Canonical authoring sequence (copy this)

See `templates/EPIC_BEAD_TEMPLATE.md` for the fill-in version. In short:

1. Write/locate the **PDR** in `08_PDRS/`.
2. Run **`/plan`** → plan doc in `.agents/plans/` (baseline audit + waves + validation blocks).
3. Create the **epic** (one `bd create --type epic`), capture its id.
4. Create **children serially**, each with `--parent`, mapped `--priority`, `--assignee`,
   and a ```` ```validation ```` block.
5. Add **deps serially** (`bd dep add`) to form waves.
6. Verify with **`bd ready`** (Wave 1 only should appear).
7. Commit the plan doc; hand off to `/pre-mortem` then `/crank`.

**Golden rule:** one `bd` write at a time. If you remember nothing else, remember that.
