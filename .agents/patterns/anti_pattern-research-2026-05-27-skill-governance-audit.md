---
name: research-2026-05-27-skill-governance-audit
type: anti-pattern
confidence: 0.50
source_learnings: [2026-05-27-skill-governance-audit]
description: Research: Most-Used Skills — Permissions, Governance, Harness Alignment
tags: []
---

# Research: Most-Used Skills — Permissions, Governance, Harness Alignment

**Backend:** inline + parallel Explore agents
**Scope:** 10 skills: rpi, crank, implement, vibe, discovery, plan, pre-mortem, post-mortem, council, validation

## Summary

All 10 skills were audited against: permissions block, governance constraints, chronicle wiring, RPI_CHRONICLE_ACTIVE flag, harness hook awareness, ratchet integration, promise markers, next-work.jsonl feeding, and workflow gaps. Verdicts: 1 ALIGNED, 7 PARTIAL, 2 MISALIGNED. The dominant failure modes are missing chronicle wiring (8/10), missing promise markers (5/10), and weak ratchet recording (5/10).

## Verdict Matrix

| Skill | Permissions | Chronicle | Ratchet | Promise | Verdict |
|-------|-------------|-----------|---------|---------|---------|
| rpi | ✅ | ✅ 4 events | ✅ implement | ✅ | PARTIAL |
| crank | ✅ | ✅ wave_complete | ❌ reads only | ✅ | MISALIGNED |
| implement | ❌ MISSING | ❌ | ✅ full | ✅ | PARTIAL |
| vibe | ✅ (contradicts) | ❌ | ⚠️ FAIL skipped | ❌ | MISALIGNED |
| discovery | ✅ | ❌ | ✅ | ✅ | PARTIAL |
| plan | ✅ (contradiction) | ❌ | ✅ | ❌ | PARTIAL |
| pre-mortem | ✅ | ❌ | ✅ | ❌ | PARTIAL |
| post-mortem | ✅ | ❌ | ❌ reads only | ❌ | PARTIAL |
| council | ✅ | ❌ | ❌ | ❌ | PARTIAL |
| validation | ✅ | ❌ standalone | ✅ vibe only | ✅ | PARTIAL |

## Critical Issues (P1)

### C1: vibe forbids Skill but workflow requires it
- `forbidden: [Skill]` in frontmatter, but Steps 4, 2e, 2g call `/council`, `/bug-hunt`, `/standards`
- Direct contradiction of own governance — three violations
- **Fix:** Change `forbidden` to allow Skill, or document that council is invoked via Agent not Skill

### C2: plan has Agent in both allowed AND forbidden
- Line 19: `allowed: [..., Agent]`; Line 20: `forbidden: [..., Agent, ...]`
- Will cause permission validation failures
- **Fix:** Remove Agent from forbidden list (it IS used in Step 3)

### C3: implement missing permissions block entirely
- No `permissions:` section in frontmatter at all
- Only skill with governance that is 100% prose-only
- **Fix:** Add permissions block matching what the skill actually does

## High Issues (P2)

### H1: Chronicle wiring absent from 8/10 skills
- Only rpi (4 events) and crank (wave_complete) write to events.jsonl
- implement, vibe, discovery, plan, pre-mortem, post-mortem, council, validation: silent
- Breaks observability chain for standalone runs

### H2: Promise markers missing from vibe, post-mortem, council, plan, pre-mortem
- These skills output verdict tables / Markdown but no `<promise>` tags
- rpi/crank check for `<promise>DONE</promise>` from sub-skills; if sub-skill skips it, orchestrator may misread result

### H3: RPI_CHRONICLE_ACTIVE never set by rpi before spawning Chronicle
- /rpi spawns Chronicle (run_in_background=True) but never exports `RPI_CHRONICLE_ACTIVE=true`
- post-mortem checks this flag for standalone feeding; if rpi doesn't set it, post-mortem double-feeds

### H4: Ratchet recording incomplete
- post-mortem: reads ratchet but never records verdicts
- council: no ratchet integration at all
- crank: reads ratchet status, never records
- validation: records vibe only (not post-mortem or retro)

## Medium Issues (P3)

- pre-mortem mandatory checks are prose-only (no Bash enforcement gates)
- plan and pre-mortem don't load harness-context.json (discovery does via STEP 0.5)
- crank's ao availability guarded at Step 0 but not at Step 8.5 (forge call)
- crank RETRY mutation logging contradicts line 126 (no mutation) vs line 614 (every change logged)
- No skill sets RPI_CHRONICLE_ACTIVE before dispatching sub-skills
- Chronicle spawn in rpi has no recovery hook — silent hang goes undetected (chronicle-requeue.sh now covers this as advisory)
- vibe ratchet skips recording on FAIL verdict (by design, but undocumented fallback for ao unavailable)

## Key Files
| File | Status |
|------|--------|
| skills/rpi/SKILL.md | PARTIAL — best overall, chronicle complete |
| skills/crank/SKILL.md | MISALIGNED — ratchet/chronicle logic split |
| skills/implement/SKILL.md | PARTIAL — no permissions block |
| skills/vibe/SKILL.md | MISALIGNED — permissions contradict workflow |
| skills/discovery/SKILL.md | PARTIAL — no chronicle, WebFetch gate unenforced |
| skills/plan/SKILL.md | PARTIAL — Agent contradiction, no promise markers |
| skills/pre-mortem/SKILL.md | PARTIAL — mandatory checks unenforced |
| skills/post-mortem/SKILL.md | PARTIAL — no ratchet record, no promise markers |
| skills/council/SKILL.md | PARTIAL — no ratchet, no chronicle, no promise markers |
| skills/validation/SKILL.md | PARTIAL — standalone chronicle gap, ratchet partial |

## Recommendations (priority order)
1. Fix vibe permissions contradiction (C1) — unblocks all vibe runs
2. Fix plan Agent contradiction (C2) — unblocks plan runs
3. Add permissions block to implement (C3)
4. Add `export RPI_CHRONICLE_ACTIVE=true` to rpi before Chronicle spawn (H3)
5. Add promise markers to vibe, post-mortem, council, plan, pre-mortem (H2)
6. Add ao ratchet record calls to post-mortem, council, crank (H4)
7. Add chronicle event writes to discovery, plan, pre-mortem (H1 — phased)
