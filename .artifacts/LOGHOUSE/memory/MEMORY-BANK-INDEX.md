# LOGHOUSE Memory Bank Index

**Purpose:** Centralized knowledge base that agents can query for lessons learned, patterns, benchmarks, and continuous improvement insights.

**Updated:** 2026-06-19  
**Agent Access:** Read-only; memory updates happen via post-mission audit process

---

## 📚 Memory Bank Sections

### 1. **Findings Database** (`findings-database.json`)
**What:** Indexed repository of all audit findings across all missions  
**Format:** JSON array of finding objects  
**Agent Access:** Query by finding_type, severity, date_range, root_cause  
**Example Query:**
```jq
.findings[] | select(.severity=="CONFIRMED" and .severity_level=="critical")
```

**Fields:**
- `mission_date` (YYYY-MM-DD)
- `finding_id` (unique)
- `type` ("bug" | "process" | "architecture" | "dependency")
- `severity_level` ("critical" | "high" | "medium" | "low")
- `status` ("CONFIRMED" | "PLAUSIBLE" | "REFUTED")
- `file` (path)
- `line` (number)
- `root_cause` (category)
- `prevention_recommendation` (string)
- `lessons_learned` (array)

**Usage:**
- Code Review Agent: Query for similar bugs to avoid repeat findings
- Audit Agent: Identify patterns, recurring issues
- Governance Bot: Trigger prevention workflows based on root_cause

---

### 2. **Lessons Learned Catalog** (`lessons-learned.md`)
**What:** Actionable insights from past missions; what we learned and will do differently  
**Format:** Markdown sections organized by category  
**Updated:** Post-mission audit (SOP-004 step 10)  
**Agent Access:** Read reference for each new mission

**Categories:**
- **Planning Lessons** — PDR quality, scope definition, risk identification
- **Execution Lessons** — Blockers encountered, workarounds, agent efficiency
- **Quality Lessons** — Bug patterns, code review findings, prevention strategies
- **Governance Lessons** — Process effectiveness, gate improvements, automation gaps
- **Scaling Lessons** — Team efficiency, parallelization opportunities, tool improvements

**Example Entry:**
```markdown
## Planning Lessons

### Lesson: Upfront PDR prevents 40% scope creep
**Mission:** 2026-06-19 (LOGHOUSE v2 build)
**Finding:** Mission with no upfront PDR had 1,614% timeline variance; retrospective PDR completion graded as B
**Recommendation:** Enforce PDR upfront (SOP-001 gate now validates content)
**Implementation:** Pre-session hook blocks if PDR validation fails
**Status:** IMPLEMENTED in CCAS-0001 v1.0
```

---

### 3. **Risk Register** (`risk-register.json`)
**What:** Cumulative risk register from all missions; recurring risks that keep emerging  
**Format:** JSON array of risk objects, indexed by probability/impact  
**Updated:** Post-mission audit (SOP-004 step 4)  
**Agent Access:** Query to pre-populate risk register for new missions

**Fields:**
- `risk_id` (unique)
- `title` (string)
- `category` ("technical" | "resource" | "timeline" | "scope" | "external")
- `first_observed` (YYYY-MM-DD)
- `frequency` (# missions where risk appeared)
- `probability` ("high" | "medium" | "low")
- `impact` ("high" | "medium" | "low")
- `recurring` (boolean — did it appear in multiple missions?)
- `mitigation_status` ("open" | "mitigated" | "closed")
- `recommended_mitigation` (string)
- `implemented_in_mission` (date of mitigation implementation)

**Example:**
```json
{
  "risk_id": "R-TIMELINE-001",
  "title": "Timeline estimation off by >50%",
  "category": "timeline",
  "first_observed": "2026-06-19",
  "frequency": 1,
  "probability": "high",
  "impact": "high",
  "recurring": true,
  "mitigation_status": "open",
  "recommended_mitigation": "Use historical benchmarks + buffer estimation; compare PDR to prior mission similar in scope"
}
```

**Usage:**
- Pre-mission: Load recurring risks into new PDR risk register
- Mid-mission: Monitor emerging risks; escalate if risk manifests
- Post-mission: Update risk frequency, mitigation status

---

### 4. **Common Blockers & Mitigations** (`blockers-and-mitigations.md`)
**What:** Patterns of blockers that recur; proven mitigations for each  
**Format:** Markdown sections, organized by blocker type  
**Updated:** Post-mission audit (SOP-004 step 5)  
**Agent Access:** Reference for execution phase; inform mid-mission decisions

**Blocker Types:**
- **External Dependency Failures** (APIs timeout, services down)
- **Scope Ambiguity** (unclear requirements, moving targets)
- **Agent Limitations** (hallucination, context limits, tool timeouts)
- **Environment Issues** (disk space, npm conflicts, path issues)
- **Decision Paralysis** (which approach, architecture option)

**Example Entry:**
```markdown
## Blocker: Scope Ambiguity

**Frequency:** 3/5 missions  
**Average Impact:** +2 hours  
**Pattern:** User request is vague; agent interprets broadly; later refining reduces scope

**Proven Mitigations:**
1. **Clarification SOP:** During PDR, explicitly ask 3 clarifying questions per objective
2. **Acceptance Criteria:** Document "done" definition upfront (not retrospectively)
3. **Mid-Mission Gate:** At 1.5 hrs, pause and confirm scope understanding with User

**Prevention for Next Mission:** Include scope clarification template in PDR-TEMPLATE.md
```

---

### 5. **Bug Patterns by Phase** (`bug-patterns-by-phase.json`)
**What:** Which types of bugs appear in which mission phases? (planning, execution, testing, deployment)  
**Format:** JSON, indexed by bug_type, phase, and root_cause  
**Updated:** Post-mission audit (SOP-004 step 9)  
**Agent Access:** Code Review Agent uses to prioritize which angles to focus on per phase

**Phases:**
- `planning` — Issues discovered during planning phase
- `execution` — Issues discovered during coding/build
- `testing` — Issues found in code review/verification
- `deployment` — Issues found post-deployment

**Example:**
```json
{
  "bug_type": "off-by-one",
  "phase": "execution",
  "frequency": 3,
  "root_cause": "loop boundary not tested",
  "severity_avg": "medium",
  "prevention": "Range-based testing required in code review angle 'simplification'"
}
```

**Usage:**
- Code Review Agent: In execution phase, heighten scrutiny on off-by-one patterns
- Audit Agent: Track whether prevention strategies are working (frequency trending down?)
- Governance Bot: Trigger enhanced code review if high-frequency bugs detected

---

### 6. **Team Efficiency Benchmarks** (`benchmarks.json`)
**What:** Historical performance data: timeline variance, scope expansion, bug rates, parallelization efficiency  
**Format:** JSON, calculated at quarterly review  
**Updated:** End of each quarter (SOP quarterly review)  
**Agent Access:** Used for forecasting and threshold setting in new missions

**Benchmark Metrics:**
```json
{
  "timeline_variance": {
    "mean": 35,
    "p25": 15,
    "p50": 32,
    "p75": 52,
    "p95": 125,
    "trend": "+3% per quarter (improving)"
  },
  "scope_expansion": {
    "mean": 18,
    "p25": 5,
    "p50": 18,
    "p75": 35,
    "p95": 95,
    "trend": "flat (stable)"
  },
  "bug_rate": {
    "confirmed_per_mission": 2.5,
    "critical_per_mission": 0.2,
    "trend": "-0.3 per quarter (improving)"
  },
  "parallelization_efficiency": {
    "target": 0.75,
    "actual": 0.68,
    "trend": "+2% per quarter (improving)"
  }
}
```

**Usage:**
- Pre-mission: Set realistic timeline estimate based on p50 variance (add buffer)
- Mid-mission: If variance is exceeding p95, escalate (SOP-002)
- Post-mission: Compare actual to benchmark; update benchmark if new data
- Quarterly: Analyze trends; adjust processes if trends are negative

---

## 🔄 Memory Update Workflow

### Post-Mission Audit (SOP-004)
**Timing:** Within 1 hour of SessionEnd  
**Owner:** Audit Agent  
**Output:** Updates to memory bank sections

**Update Process:**
1. **Findings Database** ← Add all CONFIRMED/PLAUSIBLE findings with root causes
2. **Lessons Learned** ← Document top 3 lessons from this mission
3. **Risk Register** ← Update frequency for any recurring risks; add new risks
4. **Blockers & Mitigations** ← If a new blocker type appeared, document it + mitigation
5. **Bug Patterns** ← Categorize bugs by phase and root cause; update frequency
6. **Benchmarks** ← (Skip; only updated quarterly)

### Quarterly Strategic Review
**Timing:** End of Q (Mar 31, Jun 30, Sep 30, Dec 31)  
**Owner:** Audit Agent + User  
**Output:** Trends report, updated benchmarks, strategic recommendations

**Review Process:**
1. **Aggregate metrics** — Calculate mean, percentiles, trends across all missions in quarter
2. **Update benchmarks.json** — New mean, percentile data, trend direction
3. **Trend analysis** — Are we getting better, worse, or flat?
4. **Generate trends/YYYY-Q#-health-report.md** — Executive summary with visualizations
5. **Generate trends/YYYY-Q#-recommendations.md** — Strategic improvements for next quarter

---

## 🔍 How Agents Use Memory Bank

### Code Review Agent
```
For each mission:
1. Query findings-database.json for bugs found in similar missions
2. Check bug-patterns-by-phase.json for patterns in current phase
3. Adjust code review angles to heighten scrutiny on high-frequency patterns
4. After review, update findings-database.json with new findings
```

### Audit Agent
```
For each mission:
1. Load risk-register.json; check if any risks from this mission are recurring
2. Query blockers-and-mitigations.md; check if any blockers appeared in this mission
3. After audit, update risk frequency, blocker frequency, lessons learned
4. Generate quarterly health report from benchmarks.json
```

### Governance Bot
```
For each mission:
1. Monitor timeline variance in real-time against benchmarks.p75 (yellow threshold)
2. If variance > p95, trigger advisory checkpoint (SOP-002)
3. If scope expansion > benchmarks.p75, escalate to User
4. Post-mission, update benchmarks and risk register
```

---

## 📊 Memory Bank Statistics

| Section | Records | Last Updated | Primary User |
|---------|---------|--------------|--------------|
| Findings Database | ___ | ___ | Code Review Agent |
| Lessons Learned | ___ | ___ | All agents |
| Risk Register | ___ | ___ | Audit Agent |
| Blockers & Mitigations | ___ | ___ | Governance Bot |
| Bug Patterns | ___ | ___ | Code Review Agent |
| Benchmarks | Updated quarterly | ___ | All agents |

---

## 🔐 Data Governance

**Access Control:**
- Read-only for all agents (no direct writes)
- Updates only via SOP-004 post-mission audit process
- User approval required for changes to thresholds/benchmarks

**Retention:**
- Findings: 2 years (archive older records)
- Risk Register: Current quarter + 1 prior
- Bug Patterns: All-time (trend analysis)
- Benchmarks: Quarterly snapshots (keep quarterly history)

**Privacy & Confidentiality:**
- No sensitive customer data in memory bank
- Findings anonymized (use mission ID, not details)
- Performance metrics are internal only

---

## 📝 Memory Bank File Structure

```
.artifacts/LOGHOUSE/memory/
├── MEMORY-BANK-INDEX.md              ← This file (read first)
├── findings-database.json           ← All audit findings (indexed)
├── lessons-learned.md               ← Categorical lessons & recommendations
├── risk-register.json               ← Recurring risks with mitigation status
├── blockers-and-mitigations.md      ← Common blockers + proven solutions
├── bug-patterns-by-phase.json       ← Bug types by phase (trending data)
├── benchmarks.json                  ← Performance baselines (updated quarterly)
└── archive/
    ├── 2026-Q2-benchmarks.json      ← Q2 snapshot (for trend analysis)
    ├── 2026-Q1-health-report.md     ← Q1 quarterly review
    └── ... (older snapshots)
```

---

## 🚀 Getting Started

**For agents:**
1. Read this index (MEMORY-BANK-INDEX.md)
2. For each section you need, consult the referenced JSON/MD file
3. Use jq (for JSON) or grep (for MD) to query specific data

**For humans:**
1. Post-mission audit: Follow SOP-004 step 10 to update memory bank
2. Quarterly review: Generate health report from benchmarks
3. Strategic planning: Review lessons-learned.md and risk-register.json

---

**Next:** Read individual section files for specific queries.  
**Questions?** See audit-committee-charter.md §Audit Standards §Standard 5 (SWOT & Strategic Analysis).
