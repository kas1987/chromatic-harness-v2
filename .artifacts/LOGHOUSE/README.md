# LOGHOUSE: Audit Reports Archive
**Location:** `.artifacts/LOGHOUSE/`  
**Purpose:** Centralized repository for Claude Code usage analysis, correlations, and strategic insights  
**Governance:** Updated weekly (every Friday) with comprehensive audit reports  
**Status:** ✅ Operational (Established 2026-06-19)

---

## Directory Structure

```
.artifacts/LOGHOUSE/
├── README.md                                    (this file)
├── audits/
│   ├── 2026-06-19-comprehensive-usage-analysis.md
│   ├── 2026-06-26-weekly-summary.md             (placeholder for future)
│   └── ARCHIVE/
│       └── Q2-2026/
│
├── correlations/
│   ├── 2026-06-02-tuesday-spike-git-analysis.md
│   ├── incident-response/                       (future: anomaly root causes)
│   └── pattern-library/                         (future: documented sprint patterns)
│
├── swot/
│   ├── 2026-06-19-usage-patterns-swot.md
│   ├── trends/                                  (future: quarterly SWOT evolution)
│   └── strategic-roadmap.md                     (future: recommendations tracker)
│
└── schemas/
    ├── audit-report-template.md
    └── analysis-dimensions.json
```

---

## Report Types

### 1. **Comprehensive Audit** (`audits/YYYY-MM-DD-*.md`)
**Frequency:** Weekly (Fridays)  
**Scope:** 7-day activity snapshot  
**Contents:**
- Executive summary (key metrics, anomalies)
- Session breakdown (dates, duration, intensity)
- Tool usage analysis (by category, top 10)
- Hourly/daily distribution (peak windows, off-peak)
- Workflow characteristics (read:write ratio, session continuity, automation intensity)
- Daemon lifecycle analysis
- Cache inventory and health
- Recommendations and observations

**Key Metrics Tracked:**
- Total tool invocations
- Estimated turns (tools ÷ 4.5 baseline)
- Active duration (hours)
- Peak day/hour
- Read:Write ratio
- Bash:PowerShell split
- Agent usage rate

---

### 2. **Correlation Analysis** (`correlations/YYYY-MM-DD-*.md`)
**Frequency:** On-demand (when audit reveals anomalies)  
**Scope:** Match audit spike/anomaly to git history and commit timeline  
**Contents:**
- Spike summary (metrics, intensity, duration)
- Git commit timeline during spike
- Commit categorization by phase (test, integration, stabilization, features)
- Tool invocation correlation (tools per commit, rate per phase)
- Timeline reconstruction (spike visualized against git history)
- Root cause analysis (what triggered the spike)
- Strategic implications (what it means for sprints/planning)

**Triggering Conditions:**
- Peak day represents >20% weekly activity
- Anomalous tool rate (2x baseline sustained)
- Multiple large commits in short window
- Parallel agent work (worktree merges)

---

### 3. **SWOT Analysis** (`swot/YYYY-MM-DD-*.md`)
**Frequency:** Quarterly (or after major changes)  
**Scope:** Strategic assessment of workflow strengths, weaknesses, opportunities, threats  
**Contents:**
- **Strengths:** What's working well (focus, automation, multi-agent capability)
- **Weaknesses:** What's limiting (peak-hour spikes, low agent usage, minimal task tracking)
- **Opportunities:** What could be improved (load balancing, parallelization, cache management)
- **Threats:** What could go wrong (token exhaustion, regressions, burnout, scaling limits)
- **Synthesis:** Strategic recommendations (immediate, medium-term, long-term)
- **Key Insights:** Actionable takeaways

**Review Cycle:**
- Initial SWOT: After first audit
- Quarterly refresh: Every 90 days
- Ad-hoc updates: After major workflow changes

---

## How to Use LOGHOUSE

### For Weekly Planning
1. Read the latest audit report (`audits/YYYY-MM-DD-*.md`)
2. Check for anomalies (peak concentration, unusual tool distribution)
3. Review SWOT recommendations for immediate actions
4. Plan next week with load balancing in mind

### For Root Cause Analysis
1. If an anomaly is detected in audit, check correlations
2. Match spike to git commits
3. Understand what triggered the work
4. Document in correlation analysis for future reference

### For Strategic Planning
1. Review SWOT analysis (quarterly)
2. Check trends in `swot/trends/` (if available)
3. Implement recommended improvements
4. Measure impact in subsequent audits

### For Compliance/Auditing
1. Access historical reports in `audits/` for accountability
2. Cross-reference with `correlations/` for work traceability
3. Use SWOT to demonstrate self-awareness and continuous improvement

---

## Creating a New Audit Report

### Step 1: Gather Data
```bash
# Pull audit.log
cat ~/.claude/audit.log > loghouse-audit.txt

# Get recent commits
cd chromatic-harness-v2
git log --since="7 days ago" --pretty=format:"%h %ai %s" > loghouse-commits.txt
```

### Step 2: Analyze
1. Count total tool invocations by type
2. Identify peak hours and peak days
3. Calculate read:write ratio
4. Estimate turns (tools ÷ 4.5)
5. Check for anomalies (>1.5x baseline rate, unusual tool distribution)

### Step 3: Write Report
1. Use `schemas/audit-report-template.md` as baseline
2. Fill in metrics from Step 2
3. Add executive summary highlighting anomalies
4. Include recommendations based on findings

### Step 4: Correlate (if anomalies found)
1. Pull git history for anomalous period
2. Match commit times to tool spike times
3. Categorize commits by type (test, feature, fix, chore, etc.)
4. Document correlation in `correlations/`

### Step 5: Publish
1. Save report to `audits/YYYY-MM-DD-name.md`
2. If correlation analysis created, save to `correlations/`
3. Update this README's directory structure
4. Commit and push

---

## Key Metrics Reference

### Standard Calculations
- **Estimated Turns:** `Tools ÷ 4.5` (average tools per turn during typical multi-turn conversation)
- **Tools per Hour:** `Total Tools ÷ Active Hours`
- **Peak Concentration:** `(Peak Hour Tools ÷ Total Daily Tools) × 100`
- **Read:Write Ratio:** `(Read + Read-type ops) ÷ (Write + Edit + Write-type ops)`

### Baseline Values (May 31 - Jun 4)
- **Avg Daily Tools:** 2,935
- **Avg Turns per Day:** 652
- **Avg Tools per Hour:** 234
- **Peak Hour Rate:** 1,865 tools (166% above baseline)
- **Peak Window:** 16:00-19:59 UTC (33.4% daily concentration)

### Anomaly Thresholds
- **High Activity Day:** >3,500 tools (vs. 2,935 baseline)
- **Low Activity Day:** <1,500 tools (vs. 2,935 baseline)
- **Peak Hour Spike:** >1,500 tools/hour (vs. 234 baseline)
- **Tool Rate Anomaly:** >350 tools/hour sustained (1.5x baseline)

---

## Analysis Dimensions

### Tool Categories (Hierarchical)
```
Shell Operations
├─ Bash (git, npm, CLI tools)
└─ PowerShell (Windows file ops)

File Operations
├─ Read (inspection/analysis)
├─ Edit (in-place modification)
└─ Write (new file creation)

Search & Navigation
├─ Grep (pattern matching)
└─ Glob (file discovery)

AI & Agents
├─ Agent (subagent spawning)
└─ Workflow (multi-agent orchestration)

External Integration
├─ WebFetch (HTTP requests)
├─ WebSearch (web searches)
└─ MCP Operations (multi-modal tasks)

Work Tracking
├─ TaskCreate (task initiation)
├─ TaskUpdate (task modification)
└─ TaskStop (task closure)
```

### Time Dimensions
- **Hourly:** UTC hour (00-23), peak identification, distribution
- **Daily:** Day-of-week (Mon-Sun), weekly pattern, trend
- **Weekly:** 7-day aggregate, spike detection, anomaly flagging
- **Monthly:** Long-term trends, seasonal patterns

### Workflow Dimensions
- **Session:** Continuous work block (defined by 2+ hour gaps)
- **Turn:** Multi-turn conversation (avg 4-5 tools per turn)
- **Phase:** Logical work phase (test, integration, stabilization, feature)
- **Sprint:** Weekly work unit (5 days, ~3,000 tools baseline)

---

## Integration with Other Systems

### Git Integration
- Commits linked to spike analysis in correlations
- Worktree patterns documented (multiple agents tracked)
- PR/branch automation measured via tool count surges

### Task Tracking (Future)
- TaskCreate entries linked to audit period
- Work lineage traceable through task + git correlation
- Recommendations to increase task tracking rate from 0.8% to 5%

### CI/CD Monitoring (Future)
- Daemon lifecycle correlated with CI runs
- PR automation tool counts tracked
- Build/test failures investigated via audit logs

---

## Best Practices

### Report Writing
- ✅ Include data sources (audit.log, git log, daemon.log)
- ✅ Use tables/charts for numeric data
- ✅ Highlight anomalies with clear impact statements
- ✅ Provide actionable recommendations
- ❌ Don't interpret without data backing
- ❌ Don't make assumptions about future patterns
- ❌ Don't report findings without correlation analysis

### Correlation Analysis
- ✅ Match timestamps precisely (within 5 min windows)
- ✅ Categorize commits by type (test, feature, fix, chore, deps)
- ✅ Document phase transitions (when spike changes character)
- ✅ Provide root cause hypothesis with evidence
- ❌ Don't blame tools for workflow choices
- ❌ Don't over-speculate without git evidence

### SWOT Analysis
- ✅ Base strengths/weaknesses on measurable audit findings
- ✅ Opportunities should be specific (not generic)
- ✅ Threats should include scenario + mitigation
- ✅ Recommendations should be prioritized and time-boxed
- ❌ Don't list items without evidence or context
- ❌ Don't repeat audit findings; synthesize into strategic insights

---

## Historical Data

### Baseline (May 31 - June 4, 2026)
- **14,677 total tools** across 5 days
- **3,259 estimated turns** across 62.8 hours
- **234 tools/hour baseline**, 1,865 peak/hour
- **31.4% activity concentration** on Tuesday spike
- **61% shell automation**, 30% file ops, 9% other

### Anomalies Detected
- Tuesday spike: 4,606 tools (31.4% weekly concentration)
- Peak-hour concentration: 33.4% of daily activity in 4-hour window
- Multi-agent parallelization: 8 worktree merges in 1 hour

### Established Patterns
- Monday-Tuesday ramp-up (setup → peak work)
- Wednesday-Thursday wind-down (completion → stabilization)
- 16:00-19:00 UTC = absolute peak (11 AM - 1 PM EST)
- 98.9% activity during business hours

---

## Future Enhancements

### Planned Features (Not Yet Implemented)
- [ ] Automated weekly audit generation (cron job)
- [ ] Anomaly detection alerts (when spike exceeds 2x baseline)
- [ ] Trend visualization (hourly/daily/weekly charts)
- [ ] Incident response playbooks (when regressions detected)
- [ ] Cost analysis (token spend correlation with audit metrics)
- [ ] Forecasting model (predict peak hours, needed capacity)
- [ ] Integration with CLAUDE.md (feedback loop)

### Suggested Additions
- Peak-hour advisory system (suggest deferral during 16:00-20:00 UTC)
- Task tracking enforcement (require tasks for major work)
- Cache auto-cleanup (archive pre-2026-05 CLI cache)
- Load balancing scheduler (redistribute peak work to 07:00-09:00 UTC)

---

## Support & Maintenance

### Who Maintains LOGHOUSE?
This archive is **self-serve**. You own the directory. Claude Code audit agents (when invoked) write reports here automatically.

### Troubleshooting

**Q: Audit report missing for expected date?**
A: Audit.log may have been rotated or truncated. Check `~/.claude/audit.log` file size. If <100 bytes, log was cleared (expected monthly).

**Q: Correlation analysis shows no commits during spike?**
A: Spike may be across repo boundaries. Check all repos in chromatic-* using `git log --all`.

**Q: SWOT recommendations not implemented?**
A: Use this as a backlog. Prioritize via your own sprint planning. SWOT identifies opportunities, not mandates.

**Q: Cache archive taking too long?**
A: Use `tar` to compress old cache before deletion. Example: `tar czf archive-2026-05.tar.gz CLI-cache-2026-05/*`

---

## Contact & Feedback

**Report Issues:**
- Audit reports: Check data source files for corruption
- Correlation accuracy: Verify timestamp precision (±5 min)
- SWOT actionability: Add feedback to this README's "Future Enhancements"

**Contribute:**
- Add new correlation patterns to `correlations/pattern-library/`
- Document sprint templates in `swot/`
- Create incident playbooks as you discover patterns

---

**LOGHOUSE Established:** 2026-06-19  
**Last Updated:** 2026-06-19T04:30:00Z  
**Archive Age:** 1 week  
**Next Scheduled Audit:** 2026-06-26 (Friday)  
**Status:** ✅ Operational, ready for weekly reports
