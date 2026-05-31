# Session Retrospective — KOS Pipeline + Canonical Magnets

**Date:** 2026-05-31
**PRs open:** [#55](https://github.com/kas1987/chromatic-harness-v2/pull/55) (feat/3evq-canonical-magnets — KOS + magnets)
**Also addressed:** PR #46 (harness — hardcoded path review), PR #2 claude-skills (dead-end skill routing)
**Epics closed:** `xacy` (Operating Discipline 6/6), `e00p` (BASELINE 1/1), `xerv` (TODO backlog 18/18), `9k43` (KOS pipeline 6/6)

## What shipped

### KOS Pipeline (Stages 1, 4–8)
- **Stage 1** (`o3mv`): `capture_external.py` — web/PDF/repo ingestion stub + `.agents/raw_capture/`
- **Stage 4** (`7lsm`): `extract_patterns.py` — 68 learnings → 29 patterns + 32 anti-patterns + 7 principles
- **Stage 5** (`qv3n`): `stage_candidates.py` — 32 candidates (confidence ≥ 0.7); `promote_to_wiki` gated on approved status
- **Stage 6** (`7vbb`): `review_decision.py` — `--auto` (31/32 approved), `--approve`, `--reject`; `.agents/reviews/` log
- **Stage 7** (`0yoy`): `canon_registry.yaml` (9 entries); `register_canon.py` with version + source_bead traceability
- **Stage 8** (`yz19`): `session_knowledge_feedback.py` SessionEnd hook — 28 high-confidence learnings → candidates per session

### Other work
- **4 canonical magnets** (`1uyq`): plan, dispatch, validation, decision — registered in `plugin.py` (18 magnets total)
- **BASELINE** (`4950`): `mcp_count` + `terminal_use` KPI collectors + `baseline_snapshot.py` with `--diff`
- **bd_closed_window** (`8de1`): portable closed-bead query wrapper from `.beads/issues.jsonl`
- **6 new KPI collectors**: pattern_count, candidate_count, review_coverage, canon_count, feedback_loop, capture_count
- **Stale agent bead sweep**: ~85 stale `[agent]` in-progress beads closed (SessionEnd hook now handles future ones)
- **claude-skills PR #2**: replaced dead-end `pipeline-family:plan` → `pipeline-family:implement`; removed `trust-family:test`, inlined instruction

## Learnings

### 1. KOS dependency chain as a build sequencer
Wiring `bd dep add` in stage order (4→5→6→7→8) made `bd ready` surface exactly one stage at a time. Each stage's output (patterns with confidence scores, candidates with source_ids) was the natural input for the next — no manual coordination needed between subagents.

**Action:** For any pipeline with ordered stages, create deps upfront so `bd ready` becomes the sequencer automatically.

### 2. Git rebase + index.lock from parallel subagents
When two subagents worked on overlapping branches, one left an interactive rebase in progress and a stale `.git/index.lock`. The rebase had to be aborted; the lock required a PowerShell `Remove-Item` since Bash tools weren't available.

**Action:** Dispatch parallel subagents on independent branches or confirm branch state before each agent dispatch. After any multi-agent session, run `git status` before pushing.

### 3. Skill routing to non-existent skills dead-ends workflows silently
`brainstorming/SKILL.md` routed to `pipeline-family:plan` (deleted) and `systematic-debugging/SKILL.md` routed to `trust-family:test` (deleted). Neither errored loudly — agents just couldn't proceed. The CI review bot caught both.

**Action:** After any skill deletion, grep all other SKILL.md files for references to the deleted skill name. A `scripts/validate_skill_routes.py` that checks all Skill tool references against installed skills would prevent this class of regression.

### 4. Auto-approve in review pipeline works when upstream stages enforce quality
Stage 6 `review_decision.py --auto` approved 31/32 candidates because Stage 4 (patterns) used confidence scoring and Stage 5 filtered to confidence ≥ 0.7. The review checks (confidence_ok, has_suggested_use, alignment_ok, not_duplicate) were all pre-satisfied by the time candidates arrived. This is the intended flywheel behavior.

**Action:** Trust the pipeline gates — review automation is only reliable when upstream stages enforce invariants. Don't add human review gates to compensate for weak upstream quality.

### 5. SessionEnd hooks fail-open by design — critical for harness stability
The `session_knowledge_feedback.py` hook wraps everything in try/except and exits 0 on any error. This matches the pattern in `close_stale_agent_beads.py` and `append_session_telemetry.py`. Any exception in a SessionEnd hook that exits non-zero blocks the session from closing cleanly.

**Action:** All SessionEnd hooks must be fail-open (try/except → exit 0). Never let knowledge/audit hooks break the session lifecycle.

### 6. Stale agent beads accumulate faster than the sweep runs
Even with the SessionEnd sweep hook, ~85 stale `[agent]` beads had accumulated. The hook only catches beads that were `[agent]` type at SessionEnd; beads created mid-session by orchestrators and left in-progress persist until the next sweep.

**Action:** Run `bd list --status in_progress | grep '\[agent\]'` at session start as part of GO-mode SOP, not just at end.

## KPI snapshot

| KPI | Before | After |
|---|---|---|
| Patterns extracted | 0 | 68 (29+32+7) |
| Candidates staged | 0 | 60 (32 from patterns + 28 from feedback) |
| Candidates approved | 0 | 31 auto-approved |
| Canon registry entries | 0 | 9 (6 manual + 3 seeded) |
| KPI collectors | 4 stubs | 10 (6 new + 4 original) |
| Magnets registered | 15 | 18 |
| Sessions with feedback loop | 0% | 25% (1/4) |

## Follow-up

- Merge [PR #55](https://github.com/kas1987/chromatic-harness-v2/pull/55) after CI review
- Merge PR #46 (harness) and PR #2 (claude-skills) after review
- Add `scripts/validate_skill_routes.py` — grep SKILL.md files for non-existent skill references (new bead)
- Seed canon registry with more approved candidates: `python scripts/review_decision.py --approve <name>` for remaining 28 pending
- Consider adding Stage 2/3 awareness of `.agents/raw_capture/` to auto-intake (currently just documented)
