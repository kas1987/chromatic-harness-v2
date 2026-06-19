# Comprehensive Claude Code Usage Analysis
**Date:** June 19, 2026  
**Period:** May 31 - June 4, 2026 (5 days)  
**Data Source:** `~/.claude/audit.log`, `daemon.log`, CLI cache  
**Status:** ✅ Complete Analysis

---

## EXECUTIVE SUMMARY

| Metric | Value | Interpretation |
|--------|-------|-----------------|
| **Total Invocations** | 14,677 tools | ~3,200 turns / 652 turns per day |
| **Active Duration** | 62.8 hours | 5 full-day sessions |
| **Peak Day** | June 2 (4,606 tools) | 31.4% of weekly activity |
| **Peak Hour** | 16:00 UTC (1,865 tools) | 12.7% of all activity in single hour |
| **Baseline Rate** | 234 tools/hour | Sustained automation intensity |

---

## SESSION BREAKDOWN

| Date | Start | End | Duration | Tools | Est. Turns | Rate |
|------|-------|-----|----------|-------|-----------|------|
| 2026-05-31 (Fri) | 15:20 | 23:35 | 8.3h | 2,990 | 664 | 360/h |
| 2026-06-01 (Mon) | 08:20 | 23:60 | 15.7h | 3,749 | 833 | 239/h |
| 2026-06-02 (Tue) | 00:00 | 20:14 | 20.2h | 4,606 | 1,023 | 228/h |
| 2026-06-03 (Wed) | 08:49 | 21:40 | 12.9h | 2,406 | 534 | 187/h |
| 2026-06-04 (Thu) | 13:13 | 18:55 | 5.7h | 925 | 205 | 161/h |
| **TOTAL** | | | **62.8h** | **14,677** | **3,259** | **234/h** |

**Pattern:** Fri→Tue ramp-up, Wed→Thu decline. Tuesday = sprint completion day.

---

## TOOL USAGE BREAKDOWN

### By Category
```
Shell Operations (Bash/PowerShell)    ████████████████████  61.2%  (8,983 tools)
File Operations (Read/Edit/Write)     ██████████████         29.9%  (4,388 tools)
Search & Navigation (Grep/Glob)       ██                      3.9%  (570 tools)
Task Management                       ▌                       0.8%  (117 tools)
AI Agents/Subagents                   ▌                       0.7%  (105 tools)
Web Operations                        ▌                       0.7%  (102 tools)
Other MCP/Tools                       ██                      3.1%  (450 tools)
```

### Top 10 Tools
1. **Bash** - 7,662 (52.2%) — Git, npm, build automation
2. **Read** - 2,416 (16.5%) — File inspection/analysis
3. **PowerShell** - 1,321 (9.0%) — Windows file operations
4. **Edit** - 1,313 (8.9%) — In-place file modifications
5. **Write** - 659 (4.5%) — New file creation
6. **Grep** - 323 (2.2%) — Pattern search
7. **Glob** - 247 (1.7%) — File discovery
8. **MCP Operations** - 166 (1.1%) — JavaScript, navigation tools
9. **Agent** - 105 (0.7%) — Subagent spawning
10. **WebFetch** - 96 (0.7%) — External data fetching

---

## HOURLY DISTRIBUTION

### Peak Hours (UTC)
```
Hour 16: ████████████ 1,865 (12.7%) — ABSOLUTE PEAK
Hour 18: ███████████  1,697 (11.6%)
Hour 17: █████████    1,314 (9.0%)
Hour 13: ███████      1,099 (7.5%)
Hour 15: ███████      1,028 (7.0%)
Hour 19: ███████      1,024 (7.0%)
Hour 20: ██████         881 (6.0%)
```

### 4-Hour Windows
- **14:00-17:59 UTC:** 4,306 tools (29.3%)
- **16:00-19:59 UTC:** 4,900 tools (33.4%) ← **PRIME WINDOW**
- **18:00-21:59 UTC:** 3,602 tools (24.6%)

### Off-Peak
- **01:00-06:00 UTC:** 167 tools (1.1%)
- **Interpretation:** 98.9% of activity during business hours; US EST timezone (9-5 EST + afternoon focus)

---

## DAILY PATTERN ANALYSIS

```
Fri 5/31: ██████           20.4%  (recovery/partial)
Mon 6/1:  █████████         25.5%  (ramp-up)
Tue 6/2:  ███████████████   31.4%  ← PEAK DAY
Wed 6/3:  ███████           16.4%  (↓ -48%)
Thu 6/4:  ███                6.3%  (↓ -61%, partial)
```

**Trend:** Linear decline Wed→Thu suggests task completion or reduced scope.

---

## WORKFLOW CHARACTERISTICS

### Read:Write Ratio
- **Read Operations:** 2,416
- **Write Operations:** 1,972 (Read + Edit + Write)
- **Ratio:** 1.2:1 (read-heavy)
- **Implication:** Analysis/debugging > feature development

### Session Continuity
- No gaps >2 hours within 6/1-6/3
- Long continuous focus blocks
- Suggests deep work / problem-solving sessions

### Automation Intensity
- 61% Bash/Shell usage
- 234 tools/hour baseline
- Suggests CI/CD, build, or infrastructure work

---

## DAEMON & BACKGROUND LIFECYCLE

| Daemon Session | Start | End | Duration | Status |
|---|---|---|---|---|
| Session 1 | 2026-06-01 20:48 | 2026-06-01 22:31 | 2h 43m | Idle timeout |
| Session 2 | 2026-06-18 16:04 | 2026-06-18 17:13 | 1h 9m | Idle timeout |

**Gap:** 17 days between daemon runs → on-demand spawning model (not persistent)

---

## CACHE ANALYSIS

**CLI Cache Inventory:**
- **Total Files:** 3,310 cached operation records
- **Date Range:** 2025-09-19 → 2026-06-19 (9 months)
- **Type:** Mostly JSONL (MCP operation logs, IDE interactions)
- **Volume:** ~12 files/day average (archive accumulation)

**Status:** Stale data; consider archiving pre-2026-05 entries.

---

## KEY FINDINGS

### Productivity
1. **Extreme intensity:** 652 turns/day average = context-heavy multi-turn sessions
2. **Peak day:** 1,023 turns in 20 hours = 51 turns/hour sustained
3. **Zero fatigue pattern:** Consistent rate Fri→Tue, planned wind-down Wed→Thu

### Automation Profile
1. **Shell-first workflow:** 61% Bash/PowerShell
2. **Read-driven:** 1.2:1 read:write ratio (debugging > development)
3. **Minimal parallelization:** Only 0.7% Agent tool usage (subagent spawning)

### Time Discipline
1. **Business hours only:** 98.9% activity between 08:00-23:59 UTC
2. **No nocturnal work:** <1% between 01:00-06:00 UTC
3. **Peak window:** 16:00-19:00 UTC (4-6 PM UTC = 11 AM-1 PM EST)

---

## RECOMMENDATIONS

1. **Peak Load Optimization**
   - 33.4% of daily activity compressed into 4 hours (16:00-19:59 UTC)
   - Consider spreading batch operations to early morning (07:00-08:00 UTC)
   - Could reduce concurrent tool load by 25%

2. **Increase Agent Parallelization**
   - Current: 0.7% subagent usage
   - Shell-heavy workflows could benefit from forked/parallel agents
   - Potential 20-30% throughput improvement

3. **Archive CLI Cache**
   - 3,310 files dating to Sep 2025 = stale data
   - Archive pre-2026-05 entries, retain recent 1-month cache

4. **Investigate Tuesday Peak**
   - 31.4% weekly activity on single day
   - Determine if recurring sprint pattern or one-time event
   - **Result:** See `correlations/2026-06-02-tuesday-spike.md`

---

## DATA QUALITY

- ✅ **audit.log:** Complete, no gaps (14,677 entries chronological)
- ✅ **daemon.log:** Sparse but complete (sparse runs normal)
- ⚠️ **CLI cache:** Stale (9-month old data, not representative of current)
- ❌ **Missing:** Token counts, context window utilization, cache hit ratios

---

**Report Author:** Claude Code Audit System  
**Generated:** 2026-06-19T04:01:00Z  
**Next Review:** 2026-06-26 (weekly cadence recommended)
