# Audit Report Template
**Template Version:** 1.0  
**Purpose:** Standardized structure for weekly Claude Code usage audits  
**Frequency:** Weekly (Fridays)  
**Data Sources:** `~/.claude/audit.log`, git history, daemon logs  

---

## Report Header

```markdown
# Claude Code Usage Audit Report
**Date:** YYYY-MM-DD (report generation date)  
**Period:** YYYY-MM-DD → YYYY-MM-DD (analysis period, typically 7 days)  
**Data Source:** audit.log entries, git commits, daemon logs  
**Status:** ✅ Complete / ⚠️ Partial / ❌ Incomplete
```

---

## Section 1: Executive Summary (200 words max)

**Template:**
```markdown
## EXECUTIVE SUMMARY

| Metric | Value | vs. Baseline | Interpretation |
|--------|-------|--------------|-----------------|
| **Total Invocations** | X tools | ±Y% | [Normal/High/Low] |
| **Active Duration** | X hours | ±Y% | [Intense/Moderate/Light] |
| **Peak Day** | Date (X tools) | ±Y% | [Expected/Anomalous] |
| **Avg Daily Rate** | X tools/day | ±Y% | [Sustain/Trend] |
| **Peak Hour** | HH:00 UTC (X tools) | ±Y% | [Spike/Normal] |

**Key Findings:**
- Finding 1: [Impact statement]
- Finding 2: [Impact statement]
- Anomaly: [If any]

**Recommendation:** [1-2 sentence next action]
```

**Baseline Comparison Values:**
- Avg Daily Tools: 2,935 (from May 31-Jun 4)
- Avg Turns/Day: 652
- Avg Tools/Hour: 234
- Peak Window: 16:00-19:59 UTC (33.4%)

---

## Section 2: Session Breakdown

**Template:**
```markdown
## SESSION BREAKDOWN

| Date | Start | End | Duration | Tools | Est. Turns | Rate | Notes |
|------|-------|-----|----------|-------|-----------|------|-------|
| YYYY-MM-DD | HH:MM | HH:MM | Xh | X | X | X/h | [Brief note] |
| **TOTAL** | | | **Xh** | **X** | **X** | **X/h** | |

**Observations:**
- [Pattern 1]
- [Pattern 2]
```

**Calculation Formulas:**
- Duration: end - start (hours)
- Turns: tools ÷ 4.5 (baseline avg tools per turn)
- Rate: tools ÷ duration

---

## Section 3: Tool Usage Breakdown

**Template:**
```markdown
## TOOL USAGE BREAKDOWN

### By Category
```
Shell (Bash/PowerShell)     ████...   X% (Y tools)
File Operations            ███...    X% (Y tools)
Search & Navigation        ██...     X% (Y tools)
Task Management            ▌          X% (Y tools)
AI/Agents                  ▌          X% (Y tools)
Web Operations             ▌          X% (Y tools)
Other/MCP                  ██...     X% (Y tools)
```

### Top 10 Tools
1. [Tool] - X (Y%) — [purpose]
2. ...
10. [Tool] - X (Y%) — [purpose]

**Ratios:**
- Bash:PowerShell = X:Y
- Read:Write = X:Y (indicator of analysis vs development)
```

**Category Definitions:**
- **Shell:** Bash, PowerShell commands
- **File Ops:** Read, Edit, Write tools
- **Search:** Grep, Glob
- **Task:** TaskCreate, TaskUpdate, TaskStop
- **AI/Agents:** Agent, Workflow spawning
- **Web:** WebFetch, WebSearch, MCP external

---

## Section 4: Hourly Distribution

**Template:**
```markdown
## HOURLY DISTRIBUTION

### Peak Hours (UTC, Top 5)
```
Hour HH: ████████... X (Y%)  ← [Rank]
Hour HH: ███████...  X (Y%)
...
```

### 4-Hour Windows
- **HH:00-HH:59:** X tools (Y%)
- **HH:00-HH:59:** X tools (Y%) ← PEAK WINDOW

### Off-Peak Analysis
- **01:00-06:00 UTC:** X tools (Y%)
- **Nocturnal Ratio:** Y%
- **Timezone Inference:** [EST/UTC/Other]

**Visual:** ASCII hourly bar chart (0-23 hours)
```

---

## Section 5: Daily Pattern Analysis

**Template:**
```markdown
## DAILY PATTERN ANALYSIS

### Day-of-Week Breakdown
```
Mon: ██████...    X% (Y tools)
Tue: ██████...    X% (Y tools)
Wed: ███...       X% (Y tools)
Thu: ██...        X% (Y tools)
Fri: ████...      X% (Y tools)
Sat: ▌            X% (Y tools)
Sun: ▌            X% (Y tools)
```

**Trend:** [Rising/Stable/Declining] across week

**Observations:**
- [Pattern 1]
- [Pattern 2]
```

---

## Section 6: Workflow Characteristics

**Template:**
```markdown
## WORKFLOW CHARACTERISTICS

### Read:Write Analysis
- Read Operations: X (Y%)
- Write Operations: X (Y%) [Read + Edit + Write combined]
- Ratio: X:Y
- **Implication:** [Analysis-heavy / Balanced / Development-heavy]

### Session Continuity
- Longest gap within day: X hours
- Multi-hour focus blocks: [Yes/No]
- Breaks/interruptions: [Frequent/Occasional/Rare]

### Automation Intensity
- Shell usage: X% (Bash/PowerShell heavy)
- Web integration: X% (external data fetching)
- Task tracking: X% (work lineage)

**Workflow Type:** [Debug/Feature Dev / Infrastructure / Analysis / Maintenance]
```

---

## Section 7: Anomalies & Alerts

**Template:**
```markdown
## ANOMALIES & ALERTS

| Type | Metric | Value | Baseline | Variance | Severity |
|------|--------|-------|----------|----------|----------|
| Peak Concentration | [Date] Peak % | X% | 20% | +Y% | [Low/Medium/High] |
| Hour Spike | [Hour] UTC | X tools | 234 tools/h | +Y% | [Low/Medium/High] |
| Tool Rate | [Day] Avg | X tools/h | 234 tools/h | +Y% | [Low/Medium/High] |
| Cache Growth | Files | X | Y avg | +Z | [Low/Medium/High] |

**Assessment:** [Analysis of anomalies, if any]
```

**Anomaly Thresholds (Trigger Alert):**
- Peak day > 3,500 tools
- Low day < 1,500 tools
- Peak hour > 1,500 tools
- Sustained rate > 350 tools/hour (1.5x baseline)

---

## Section 8: Correlation Analysis (If Anomalies Found)

**Template:**
```markdown
## CORRELATION ANALYSIS

**Anomaly:** [Description of spike/anomaly]
**Period:** YYYY-MM-DD HH:MM → HH:MM UTC

### Git History During Period
- Total commits: X
- By type: X test, X feature, X fix, X chore, X deps
- Largest commit: [message] (Y files changed)

### Timeline Reconstruction
- Phase 1 (HH:MM-HH:MM): [Description] — X tools
- Phase 2 (HH:MM-HH:MM): [Description] — X tools
- ...

### Root Cause
**Hypothesis:** [What triggered the spike]
**Evidence:** [Git commits, tool breakdown]
**Confidence:** [High/Medium/Low]

### Strategic Implication
[One paragraph on what the spike means for future sprints]
```

---

## Section 9: Daemon & Infrastructure

**Template:**
```markdown
## DAEMON & INFRASTRUCTURE

| Session | Start | End | Duration | Status | Workers | Notes |
|---------|-------|-----|----------|--------|---------|-------|
| X | YYYY-MM-DD HH:MM | YYYY-MM-DD HH:MM | Xh Ym | [Idle timeout/Shutdown/Error] | X | |

**Observations:**
- Daemon spawn frequency: [Rare/Occasional/Frequent]
- Uptime per session: [Long/Moderate/Short]
- Cache accumulation: X files/day
```

---

## Section 10: Recommendations

**Template:**
```markdown
## RECOMMENDATIONS

### Immediate (This Week)
1. [Action] → [Expected outcome]
2. [Action] → [Expected outcome]

### Short-term (1-2 Weeks)
1. [Action] → [Expected outcome]
2. [Action] → [Expected outcome]

### Strategic (1+ Months)
1. [Action] → [Expected outcome]
2. [Action] → [Expected outcome]
```

**Recommendation Scoring:**
- ✅ High Impact / Low Effort → Do First
- 🟡 Medium Impact / Medium Effort → Backlog
- ❌ Low Impact / High Effort → Defer

---

## Section 11: Data Quality Notes

**Template:**
```markdown
## DATA QUALITY

| Source | Status | Completeness | Notes |
|--------|--------|--------------|-------|
| audit.log | ✅ | Y% | [Gaps/truncations, if any] |
| git log | ✅ | Y% | [Missing repos/branches, if any] |
| daemon.log | ⚠️ | Y% | [Sparse but complete] |
| CLI cache | ❌ | Y% | [Stale data, archive recommended] |

**Limitations:**
- [Missing data type]
- [Known gaps]
- [Assumptions made]
```

---

## Section 12: Metadata

**Template:**
```markdown
## REPORT METADATA

- **Report ID:** AUDIT-YYYY-MM-DD-[hash]
- **Generated:** YYYY-MM-DDTHH:MM:SSZ
- **Author:** Claude Code Audit System
- **Next Review:** YYYY-MM-DD (typically 7 days later)
- **Archive Location:** `.artifacts/LOGHOUSE/audits/`
- **Correlation Reports:** [Link if created]
- **Approval Status:** ✅ Ready / 🔄 Pending Review / ❌ Needs Revision
```

---

## Filling in the Template

### Step 1: Data Gathering
```bash
# Pull audit log
cat ~/.claude/audit.log | tee audit-extract.txt

# Count tools by type
grep -o '\] [A-Za-z]*$' audit-extract.txt | sort | uniq -c

# Get date range
head -1 audit-extract.txt  # Start
tail -1 audit-extract.txt  # End
```

### Step 2: Analysis
- Parse timestamps, calculate sessions/turns
- Group by hour, day, tool type
- Identify anomalies (>1.5x baseline)
- Calculate ratios (read:write, bash:ps, etc.)

### Step 3: Git Correlation (if anomalies)
```bash
# Get commits during anomaly window
git log --since="YYYY-MM-DD HH:MM" --until="YYYY-MM-DD HH:MM" \
  --pretty=format:"%h %ai %s" -- .
```

### Step 4: Write Report
- Fill sections 1-12 using template
- Use tables/charts for numeric data
- Include evidence for all claims
- Highlight anomalies with impact statements

### Step 5: Publish
```bash
# Save report
cp report.md .artifacts/LOGHOUSE/audits/YYYY-MM-DD-title.md

# Commit
git add .artifacts/LOGHOUSE/
git commit -m "audit: weekly report YYYY-MM-DD"
git push
```

---

## Example Entry: Complete Session Row

```markdown
| 2026-06-02 | 00:00 | 20:14 | 20.2h | 4,606 | 1,023 | 228/h | Tuesday spike: multi-agent test suite + infrastructure sprint |
```

---

## Common Pitfalls

❌ **Don't:**
- Interpret without data backing
- Report absolute numbers without baseline context
- Make assumptions about causation (use "correlation" language)
- Leave anomalies unanalyzed
- Mix past/present tense

✅ **Do:**
- Compare vs. 2935 daily baseline, 234 tools/hour baseline
- Use percentages + absolute numbers (transparency)
- Say "associated with" rather than "caused by"
- Investigate spikes via git correlation
- Use past tense for audit period, present for recommendations

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-06-19 | Initial template based on first audit |

---

**Template Author:** Claude Code Audit System  
**Last Updated:** 2026-06-19  
**Status:** ✅ Ready for Use
