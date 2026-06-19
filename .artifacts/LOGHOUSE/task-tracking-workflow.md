# Task Tracking Workflow: bd (Beads) Integration
**Status:** ✅ Implemented  
**Target:** Increase task tracking from 0.8% to 5%  
**Lineage:** turn → bead → commit → audit report

---

## Overview

This document describes how to track work using **beads** (bd tasks) to create full sprint lineage and improve observability of what work was done and why.

**Problem:** Current audit shows only 0.8% task operations (117 tasks for 3,259 turns). Work context is lost.

**Solution:** Integrate beads into workflow to link:
- 🔄 Turns (Claude Code conversations)
- 📝 Beads (work units/tasks)
- 💾 Commits (git history)
- 📊 Audit reports (LOGHOUSE)

**Target:** 5% of operations involve task tracking (163+ explicit beads per week).

---

## Quick Start

### 1. Create a Bead When Starting Major Work

```bash
~/.claude/bin/create-bead.sh \
  --title "Load balancing peak hour work" \
  --priority P1 \
  --timeline "3h" \
  --description "Redistribute 25% of 16:00-19:59 UTC activity to early morning"
```

**Output:**
```
✅ Bead created: bead-1719846000-a1b2c3
📝 Location: ~/.beads/active/bead-1719846000-a1b2c3.md
🏷️  Title: Load balancing peak hour work
⚡ Priority: P1
⏱️  Timeline: 3h

Use this ID to link work:
  - Reference in commit messages: [BEAD=bead-1719846000-a1b2c3]
  - Link turns: update-bead.sh --id bead-1719846000-a1b2c3 --link-turn <turn>
  - Mark done: update-bead.sh --id bead-1719846000-a1b2c3 --status completed
```

### 2. Reference Bead During Work

**In commit messages:**
```bash
git commit -m "feat: load balancing cron setup [BEAD=bead-1719846000-a1b2c3]"
```

**In Claude Code conversations:**
When starting a new session on this work, mention:
> Working on BEAD=bead-1719846000-a1b2c3: Load balancing peak hour work

### 3. View All Beads

```bash
~/.claude/bin/show-beads.sh
```

**Output:**
```
🔴 ACTIVE BEADS
─────────────────────────────────────────────────────
  [P1] Load balancing peak hour work
    ID: bead-1719846000-a1b2c3 | Timeline: 3h

  [P2] Cache cleanup automation
    ID: bead-1719847000-d4e5f6 | Timeline: 1h

✅ COMPLETED BEADS (Last 5)
─────────────────────────────────────────────────────
  ✓ LOGHOUSE server implementation
    ID: bead-1719845000-z1y2x3

📊 Summary: 2 active | 1 completed
```

### 4. Mark Bead as Complete

```bash
update-bead.sh --id bead-1719846000-a1b2c3 --status completed
```

Moves bead from `~/.beads/active/` to `~/.beads/completed/`.

---

## Workflow Integration Points

### During Session Start
**Reference your bead:**
```
Me: Working on BEAD=bead-1719846000-a1b2c3: Load balancing peak hour work

[description of what needs to be done]
```

**Why:** This establishes the turn ↔ bead connection in Claude Code's audit logs.

### During Implementation
**Add to commits:**
```bash
git commit -m "feat: load balancing rules [BEAD=bead-1719846000-a1b2c3]"
```

**Why:** Creates bead ↔ commit linkage automatically (LOGHOUSE will scan for `[BEAD=...]`).

### During Results
**Document in bead file:**
```bash
# Edit ~/.beads/active/bead-1719846000-a1b2c3.md

## Linked Work
**Turns:**
- Turn 1: Initial analysis
- Turn 2: Implementation

**Commits:**
- 6fb8cc1 feat: load balancing rules

**Audit Reports:**
- audits/2026-06-20-load-balancing-results.md
```

**Why:** LOGHOUSE can correlate all work to generate comprehensive audit trail.

### During Completion
**Mark done:**
```bash
update-bead.sh --id bead-1719846000-a1b2c3 --status completed
```

**Why:** Completed beads are archived for historical reference.

---

## Bead Structure

Each bead file (`.beads/active/BEAD_ID.md`) contains:

```markdown
# Title of Work

**Bead ID:** bead-1719846000-a1b2c3
**Priority:** P0 | P1 | P2 | P3
**Timeline:** 30m | 2h | 1d | 2d
**Created:** 2026-06-19T10:00:00Z
**Status:** active | in-progress | completed

## Description
[Problem, solution, success criteria]

## Linked Work
- Turns: (TBD - filled during implementation)
- Commits: (TBD - auto-linked via [BEAD=...] in commit messages)
- Audit Report: (TBD - linked during review)

## Progress
- [ ] Started
- [ ] In Progress
- [ ] Completed
- [ ] Reviewed
```

### Priority Levels

| Priority | Use Case | SLA |
|----------|----------|-----|
| **P0** | Release blocker, security issue | Immediate |
| **P1** | Sprint goal, high-value work | This week |
| **P2** | Nice-to-have, backlog item | Next sprint |
| **P3** | Polish, follow-up | Whenever |

---

## LOGHOUSE Integration

### Automatic Linking

The LOGHOUSE system automatically:

1. **Scans commits** for `[BEAD=...]` references
2. **Matches timestamps** to correlate turns → beads
3. **Groups by bead** to show all related work
4. **Generates reports** showing full lineage

### Example: Turn → Bead → Commit → Audit

```
Turn 2 (2026-06-19 10:30)
  ↓ References BEAD=bead-1719846000-a1b2c3
Bead: "Load balancing peak hour work"
  ↓ Linked via commit reference
Commit 6fb8cc1: "feat: load balancing [BEAD=bead-1719846000-a1b2c3]"
  ↓ Correlated in audit
Audit: audits/2026-06-20-load-balancing-results.md
  ├─ Shows this work
  ├─ Metrics: peak hour 1,225 → 920 tools/hour
  └─ Links back to: BEAD=bead-1719846000-a1b2c3
```

### Querying Related Work

```bash
# Find all work for a bead
grep -r "bead-1719846000-a1b2c3" ~/.beads chromatic-harness-v2/.artifacts/LOGHOUSE

# Find all commits for a bead
cd chromatic-harness-v2 && git log --all --grep="BEAD=bead-1719846000-a1b2c3"

# View audit results
cat chromatic-harness-v2/.artifacts/LOGHOUSE/audits/*bead*
```

---

## Best Practices

### Do

✅ **Create a bead before starting major work**
- Especially for sprint goals or action items
- Use clear, descriptive titles
- Set realistic timelines

✅ **Reference bead in commits**
```bash
git commit -m "implementation [BEAD=bead-xyz]"
```

✅ **Update progress in bead file**
- Mark status as you work
- Add links to related audits
- Document challenges/learnings

✅ **Complete and archive beads**
- Closes out the work unit
- Preserves history for future reference
- Improves turnover data for insights

### Don't

❌ **Create too many fine-grained beads**
- Aim for ~5 beads/week (sprint-level work)
- Not every small fix needs a bead
- Focus on meaningful work units

❌ **Forget to reference in commits**
- `[BEAD=...]` is what links the dots
- Without it, work is orphaned in git history

❌ **Leave beads stale**
- Close completed beads promptly
- Update status regularly
- Archive old work

---

## Scripts

### Available Commands

**Create bead:**
```bash
~/.claude/bin/create-bead.sh \
  --title "Work title" \
  --priority P0-P3 \
  --timeline "2h" \
  --description "Optional details"
```

**Show all beads:**
```bash
~/.claude/bin/show-beads.sh
```

**Update bead status:**
```bash
~/.claude/bin/update-bead.sh \
  --id bead-1719846000-a1b2c3 \
  --status completed
```

**View bead details:**
```bash
cat ~/.beads/active/bead-1719846000-a1b2c3.md
```

---

## Measuring Success

### Current Baseline
- **Task tracking rate:** 0.8% (117 tasks, 14,677 tools)
- **Task-to-turn ratio:** 1:28 (most turns undocumented)
- **Work traceability:** Lost (no turn → commit → audit link)

### Target
- **Task tracking rate:** 5% (163+ tasks per week equivalent)
- **Task-to-turn ratio:** 1:6 (most sprints tracked)
- **Work traceability:** Complete (every bead → audit report)

### Metrics to Track

Track these in weekly audits:

```
Week of 2026-06-19:
  - Beads created: 5
  - Beads completed: 2
  - Avg timeline accuracy: 85%
  - Turn coverage: 30% of turns reference a bead
  - Commit coverage: 40% of commits reference a bead
```

---

## Example: Load Balancing Bead

**Created:**
```bash
create-bead.sh \
  --title "Load balancing peak hour reduction" \
  --priority P1 \
  --timeline "3h" \
  --description "Redistribute 25% of 16:00-19:59 UTC to early morning (07:00-09:00)"
```

**During work:**
```
Turn 1 (Turn analysis):
  > Working on BEAD=bead-1719846000-a1b2c3: Load balancing...
  [analysis and planning]

Turn 2 (Implementation):
  > Continuing BEAD=bead-1719846000-a1b2c3...
  [build cron schedule]

Commit:
  git commit -m "feat: load balancing cron [BEAD=bead-1719846000-a1b2c3]"
```

**After completion:**
```bash
# Update bead file
cat >> ~/.beads/active/bead-1719846000-a1b2c3.md << EOF

## Linked Work
**Turns:** Turn 1 (analysis), Turn 2 (implementation)
**Commits:** 6fb8cc1 feat(schedule): load balancing cron
**Audit:** audits/2026-06-20-load-balancing-results.md

## Results
- Peak hour rate: 1,225 → 920 tools/hour (-25%)
- Early morning activity: +500 tools
- Status: ✅ Complete, results reviewed
EOF

# Mark as done
update-bead.sh --id bead-1719846000-a1b2c3 --status completed
```

**Audit correlation:**
```
LOGHOUSE audit scans and finds:
  - Commits with [BEAD=bead-1719846000-a1b2c3]
  - Correlates to turn references
  - Links to results audit
  - Generates report: "Load balancing results"
```

---

## FAQ

**Q: When should I create a bead?**
A: When starting work that will take >30 min or involves multiple turns/commits. Quick 5-min fixes don't need beads.

**Q: Can I create beads retroactively?**
A: Yes, you can create beads for past work and backfill the linked work section (turns, commits). Just add the bead ID to future commit messages.

**Q: What if a bead takes longer than estimated?**
A: Update the timeline field as you learn. LOGHOUSE uses actual timelines to calibrate estimates.

**Q: How do I link multiple commits to one bead?**
A: Use the same `[BEAD=...]` reference in each commit message. LOGHOUSE groups them by bead ID.

**Q: Where's the data stored?**
A: `~/.beads/active/` for active work, `~/.beads/completed/` for historical.

---

**Workflow Version:** 1.0  
**Implemented:** 2026-06-19  
**Target Rate:** 5% of operations involve beads  
**Success Metric:** Full turn → bead → commit → audit lineage
