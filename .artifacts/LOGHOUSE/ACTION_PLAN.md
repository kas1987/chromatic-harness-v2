# LOGHOUSE Implementation Action Plan
**Generated:** 2026-06-19  
**Status:** Planning phase (ready for execution)  
**Authority:** SWOT + Audit correlation analysis  

---

## PHASE 1: FINDINGS SYNTHESIS

### Top 5 Action Items (Priority Ranked)

| # | Action | Effort | Impact | Owner | Timeline | Status |
|---|--------|--------|--------|-------|----------|--------|
| 1 | **Load Balancing** — Redistribute 25% of peak (16:00-19:59 UTC) work to 07:00-09:00 UTC | Low | High | You | This sprint | 🔴 Not started |
| 2 | **Task Tracking** — Increase from 0.8% to 5% task operations; integrate into sprint workflow | Low | High | You | This sprint | 🔴 Not started |
| 3 | **Cache Cleanup** — Archive pre-2026-05 CLI cache, retain 30-day recent; 40% footprint savings | Low | High | You | This sprint | 🔴 Not started |
| 4 | **Agent Parallelization** — Convert sequential shell ops to forked agents; start with git operations | Medium | High | Future | 1-2 sprints | 🔴 Not started |
| 5 | **Audit Automation** — Weekly report generation + anomaly alerts; cron job or hook-based | Medium | Medium | Future | 1-2 sprints | 🔴 Not started |

### Quick Wins (Low Effort, High Impact)
✅ Load balancing, task tracking, cache cleanup — all executable this sprint with <4 hours effort total

### Strategic Dependencies
- Load balancing enables: better resource allocation, reduced peak-hour throttling risk
- Task tracking enables: audit correlation (turn → task → commit), regression prevention
- Cache cleanup enables: faster startup, reduced context bloat
- Agent parallelization depends on: task tracking (need work units to distribute)
- Audit automation depends on: stable task tracking + audit log consistency

---

## PHASE 2: IMMEDIATE ACTIONS (THIS SPRINT)

### Action 1: Load Balancing Strategy

**Objective:** Reduce peak-hour (16:00-19:59 UTC) concentration from 33.4% to ~25%

**Current State:**
- 4,900 tools in 4-hour peak window (1,225 tools/hour)
- 166 tools/hour in early morning (07:00-09:00 UTC, typically 0-100)
- 33.4% of daily volume squeezed into 4 hours

**Target State:**
- Redistribute 25% of peak load (~1,225 tools) to early morning
- Reduce peak from 1,225 tools/hour to 920 tools/hour
- Increase early morning from 0-100 to 300-400 tools

**Implementation Plan:**

1. **Identify Batch Operations (This Week)**
   - Git syncs (multi-repo fetch, status, pull)
   - Dependency updates (npm audit, PyPI checks)
   - Report generation (LOGHOUSE audits, CI summaries)
   - Cache maintenance (archival, cleanup)
   - **Estimated:** 25-30% of peak work is batchable

2. **Create Deferral Rules (Week 1)**
   - Mark operations as "deferrable" (non-urgent, can run off-peak)
   - Create scheduling decision tree:
     - If 16:00-19:59 UTC AND deferrable → defer to 07:00-09:00 UTC
     - If interactive/urgent → run immediately
   - Document in project README

3. **Implement Scheduling (Week 1)**
   - Add `--defer-to-early-morning` flag to batch scripts
   - Create cron job: 07:00 UTC runs deferred batch operations
   - Test: one deferred operation in real sprint

4. **Monitor & Adjust (Ongoing)**
   - Track peak-hour load reduction via weekly audit.log
   - Measure: Is peak dropping from 1,225 to 920 tools/hour?
   - Adjust deferral list if threshold not met

**Success Metrics:**
- Peak-hour rate: 1,225 → 920 tools/hour (25% reduction)
- Early-morning rate: 50 → 300 tools/hour (6x increase)
- Peak window concentration: 33.4% → 25% of daily
- No regression in overall daily tools (should stay ~2,900)

**Effort:** 2-3 hours (rules + cron job + testing)

---

### Action 2: Task Tracking Integration

**Objective:** Increase task operations from 0.8% (117 tasks for 3,259 turns) to 5% (163+ tasks per 3,259 turns)

**Current State:**
- Only 117 TaskCreate/Update/Stop operations in 14,677 total tools
- Work tracking ad-hoc; regressions harder to prevent
- No sprint lineage from turns → task → commit

**Target State:**
- Require TaskCreate for every major work phase (test, integration, stabilization, feature)
- Link task IDs to audit logs and git commits
- Sprint context visible in task descriptions

**Implementation Plan:**

1. **Define Task Triggers (Week 1)**
   - When to create task: major feature, infrastructure work, bug fix with >5 tools expected
   - When to update task: phase transition (started → in_progress → code_review → done)
   - When to close task: sprint phase complete, work shipped
   - Document in project README: "Task Tracking Rules"

2. **Create Task Template (Week 1)**
   ```
   Task: [Feature/Bug/Infrastructure]
   Description: [What + Why]
   Expected tools: [Estimated tool count, e.g., 50-100]
   Expected duration: [Hours]
   Dependencies: [Other tasks/commits]
   ```

3. **Integrate into Workflow (Week 2)**
   - Before starting major work: run `bd create` or TaskCreate
   - Capture task ID in commit messages: `task: TASK-ID: commit message`
   - Link audit log entry to task (note task ID when hitting 10+ tools)

4. **Monitor & Report (Ongoing)**
   - Weekly audit should show task % rising from 0.8% to 5%
   - Tools-per-task ratio normalizing (currently undefined)
   - Audit reports will include task lineage analysis

**Success Metrics:**
- Task operations: 117 → 500+ across 3,259 turns (5% of work tracked)
- Sprint visibility: 100% of major work linked to tasks
- Regression prevention: 0 untracked changes
- Audit reports can correlate turns → task → commit

**Effort:** 1-2 hours (template + rules + documentation)

**Note:** Project uses `bd` (beads) for task tracking per CLAUDE.md, not TaskCreate. Recommend using `bd create` workflow instead.

---

### Action 3: Cache Cleanup & Archival

**Objective:** Archive pre-2026-05 CLI cache; reduce footprint 40%, faster startup

**Current State:**
- 3,310 CLI cache files in `~/.claude/AppData/Local/claude-cli-nodejs/`
- Date range: 2025-09-19 → 2026-06-19 (9 months old)
- Size: ~8.7 MB accumulating daily
- Never cleaned; historical noise

**Target State:**
- Retain only last 30 days of cache (recent 1-month active)
- Move pre-2026-05 cache to `.artifacts/LOGHOUSE/archive/cache-2026-05-archive/`
- Create auto-cleanup script for future (runs monthly)

**Implementation Plan:**

1. **Inventory Pre-2026-05 Cache (This Week)**
   ```bash
   find ~/.claude/AppData/Local/claude-cli-nodejs -mtime +19 \
     -o -newermt "2026-05-01" -o -oldermt "2026-05-01"
   # Identify files older than May 1, 2026
   ```
   - Estimate: ~80-90% of 3,310 files are pre-2026-05

2. **Archive (Week 1)**
   ```bash
   # Create archive directory
   mkdir -p .artifacts/LOGHOUSE/archive/cache-2026-05-archive
   
   # Move pre-2026-05 cache
   find ~/.claude/AppData/Local/claude-cli-nodejs -mtime +19 \
     -exec mv {} .artifacts/LOGHOUSE/archive/cache-2026-05-archive/ \;
   
   # Compress for storage
   tar czf .artifacts/LOGHOUSE/archive/cli-cache-2026-05.tar.gz \
     .artifacts/LOGHOUSE/archive/cache-2026-05-archive/
   
   # Cleanup source
   rm -rf .artifacts/LOGHOUSE/archive/cache-2026-05-archive/
   ```

3. **Implement Auto-Cleanup (Week 2, Optional)**
   - Create `scripts/cache-cleanup.sh`
   - Add cron job: `0 0 1 * * bash scripts/cache-cleanup.sh` (1st of month, midnight)
   - Retention policy: keep only last 30 days

4. **Monitor (Ongoing)**
   - Track CLI cache size in weekly audit
   - Verify no startup slowdown post-cleanup
   - Measure: Is cache size now 2-3 MB instead of 8.7 MB?

**Success Metrics:**
- Cache footprint: 8.7 MB → 2.5 MB (71% reduction)
- Files retained: 3,310 → ~300 (last 30 days)
- Startup performance: No regression (measure time)
- Archive: Pre-2026-05 cache safely stored for historical reference

**Effort:** 1 hour (archival + script)

---

## PHASE 3: AUDIT AUTOMATION SETUP

### Weekly Audit Schedule

**Frequency:** Every Friday 18:00 UTC  
**Duration:** ~5 minutes (automated, no manual input)  
**Output:** Report auto-stored in `.artifacts/LOGHOUSE/audits/`

**Proposed Cron Job:**
```bash
# Add to crontab or Claude settings.json SessionEnd hook
0 18 * * FRI python scripts/audit_loghouse_weekly.py
```

**Script Location:** `scripts/audit_loghouse_weekly.py` (to be created)
- Reads `~/.claude/audit.log`
- Parses tools by hour/day/type
- Generates markdown report using template
- Commits to git automatically
- Sends summary notification (optional)

---

### Anomaly Alert Thresholds

**Trigger Investigation When:**
| Metric | Threshold | Action |
|--------|-----------|--------|
| Daily tools | >4,000 (1.4x baseline 2,935) | Flag in audit report, create correlation investigation |
| Peak hour | >1,500 tools (6.4x baseline 234/hour) | Alert, review concurrent load |
| Sustained rate | >350 tools/hour (1.5x baseline) | Warning, check for runaway processes |
| Read:Write ratio | Inverts (<1.0 or >2.0) | Alert, suggests crisis mode or heavy cleanup |
| Agent usage | Drops <0.5% | Warning, suggest re-enabling parallelization |
| Task tracking | Drops <0.5% | Alert, work becoming untracked |

**Auto-Escalation:**
- Level 1: Note in audit report, no action
- Level 2: Trigger correlation analysis (git history matching)
- Level 3: Send summary notification to user
- Level 4: (Future) Auto-create bd task for investigation

---

## PHASE 4: DOCUMENTATION

### 1. Project-Specific LOGHOUSE README

**File:** `LOGHOUSE_PROJECT_README.md` (to be created in `.artifacts/LOGHOUSE/`)

**Contents:**
- How to use LOGHOUSE for chromatic-harness-v2 project
- Integration with bd task tracking
- Weekly audit cadence and report access
- When to investigate anomalies
- Reference to parent LOGHOUSE README

**Key Section: Chromatic-Harness-V2 Specific**
- Link Tuesday spike pattern to project's multi-agent architecture
- Document repeatable test suite + infrastructure sprint pattern
- Reference parallel worktree branches + merge strategy
- Note: This project's 31.4% peak Tuesday is EXPECTED (planned sprint)

---

### 2. Add LOGHOUSE References to Main README

**File:** `README.md` (update existing)

**Add Section:**
```markdown
## Observability & Audit Reports

See [LOGHOUSE](.artifacts/LOGHOUSE/) for weekly usage audits, spike analysis, and strategic recommendations.

- Latest audit: [2026-06-19](.artifacts/LOGHOUSE/audits/2026-06-19-comprehensive-usage-analysis.md)
- Spike correlations: [Tuesday 6/2 analysis](.artifacts/LOGHOUSE/correlations/2026-06-02-tuesday-spike-git-analysis.md)
- Strategic SWOT: [2026-06-19 assessment](.artifacts/LOGHOUSE/swot/2026-06-19-usage-patterns-swot.md)
```

---

### 3. Create Claude Hook Reminder

**File:** Add to `settings.json` or `.claude.json`

**Hook Type:** PrePush

**Content:**
```json
{
  "PrePush": {
    "message": "📊 Remember: Check LOGHOUSE (.artifacts/LOGHOUSE/) for weekly audit insights and recommendations",
    "enabled": true
  }
}
```

This reminds on every push to review latest audit reports.

---

## PHASE 5: CONSOLIDATED ACTION PLAN

### Summary Table

| Priority | Action | Effort | Impact | Timeline | Owner | Status |
|----------|--------|--------|--------|----------|-------|--------|
| 🔴 P0 | Load balancing (redistribute 25% peak) | 2-3h | High | Week 1 | You | To do |
| 🔴 P0 | Task tracking (0.8% → 5%) | 1-2h | High | Week 1 | You | To do |
| 🔴 P0 | Cache cleanup (archive pre-2026-05) | 1h | High | Week 1 | You | To do |
| 🟡 P1 | Audit automation (weekly reports) | 3-4h | Medium | Week 2 | Future | To do |
| 🟡 P1 | Anomaly alert thresholds | 1-2h | Medium | Week 2 | Future | To do |
| 🟡 P1 | Documentation (README updates, hooks) | 1h | Low | Week 2 | You | To do |
| 🔵 P2 | Agent parallelization | Medium | High | Sprint 2 | Future | To do |
| 🔵 P2 | Web integration enhancement | Medium | Medium | Sprint 2 | Future | To do |

### By Timeline

**This Week (Week 1, June 19-25):**
1. Load balancing rules + cron job (2-3h)
2. Task tracking template + workflow (1-2h)
3. Cache archive script (1h)
4. Total: 4-6 hours
5. Expected impact: 25% peak reduction, task visibility, cache bloat eliminated

**Next Week (Week 2, June 26-July 2):**
1. Audit automation script (3-4h)
2. Anomaly alert thresholds (1-2h)
3. Documentation updates (1h)
4. Cron job testing (1h)
5. Total: 6-8 hours
6. Expected impact: Weekly reports running, anomalies detected automatically

**Future (Sprints 2+):**
1. Agent parallelization (medium effort, high impact)
2. Web integration (medium effort, medium impact)
3. Audit report enhancement (continuous)

### Success Criteria

**Week 1:**
- ✅ Peak-hour rate reduced from 1,225 to 920 tools/hour (25% drop)
- ✅ Task operations visible in audit (0.8% → 2%+)
- ✅ Cache footprint reduced 40%
- ✅ Zero regressions in daily tools

**Week 2:**
- ✅ First automated audit report generated Friday 18:00 UTC
- ✅ Anomaly thresholds documented
- ✅ Zero manual audit work needed

**Month 1:**
- ✅ 4 automated weekly audits collected
- ✅ Trends visible (peak load stabilizing, task tracking rising)
- ✅ Agent parallelization pilot started

**Quarter 1:**
- ✅ 12 weekly audits archived
- ✅ SWOT refreshed (quarterly)
- ✅ Actionable trends documented
- ✅ 2+ recommendations implemented

---

## Dependencies & Blockers

**Hard Dependencies:**
- Task tracking (bd) must be working before automation can link tasks
- Audit.log must not be rotated weekly (need 7-day retention)

**Soft Dependencies:**
- Load balancing effectiveness depends on accurate peak-hour identification (audit provides this)
- Agent parallelization effectiveness depends on task tracking being in place

**Known Blockers:**
- None identified; all actions are low-friction

---

## Owner & Accountability

| Action | Owner | Notes |
|--------|-------|-------|
| Load balancing | You | Rules + cron job, you understand peak pattern best |
| Task tracking | You | Set rules for your own workflow |
| Cache cleanup | You | One-time operation, then automated |
| Audit automation | Future | Can delegate to shared infrastructure agent |
| Alert thresholds | You | Define based on your risk tolerance |
| Documentation | You | Only you know the project context |
| Agent parallelization | Future | Requires architectural discussion |

---

## Metrics for Measuring Success

**Weekly Audit Will Track:**
- Peak-hour tool rate (target: 920/hour, from 1,225)
- Task operations % (target: 5%, from 0.8%)
- Cache size (target: 2.5 MB, from 8.7 MB)
- Daily total tools (target: stable 2,900, no degradation)

**Quarterly SWOT Will Update:**
- Revisit weaknesses (should see improvements on tracked metrics)
- Assess new opportunities (from successful implementations)
- Identify new threats (from changing usage patterns)

---

**Action Plan Status:** 🟢 Ready for Implementation  
**Next Step:** Execute Week 1 items (load balancing, task tracking, cache cleanup)  
**Review Date:** 2026-06-26 (Friday) — First automated audit will show progress
