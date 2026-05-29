---
name: harvest-insights
description: Parses the latest /insights report and autonomously generates PDRs, queues items into next-session-queue, writes an audit record, and updates the meta-brain. Run after every /insights call or on a weekly schedule.
---

# /harvest-insights — Autonomous Insights → PDR Pipeline

> **Quick Ref:** Turns `/insights` output into structured PDRs, beads queue entries, audit trail, and meta-brain learnings. Runs fully autonomous — no human gates.

**YOU MUST EXECUTE THIS WORKFLOW. Do not just describe it.**

## When to Use

- After running `/insights` manually
- On weekly schedule (see Step 6 for cron setup)
- After any significant session milestone (50+ sessions, major friction pattern identified)

## Execution Steps

### Step 1: Locate Insights Data

Check for a JSON report first, then fall back to the latest HTML:

```powershell
# Newest JSON report
$report = Get-ChildItem "$HOME\.claude\usage-data\report-*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

# If no JSON, check HTML (insights data is embedded)
if (-not $report) {
  $report = Get-ChildItem "$HOME\.claude\usage-data\report-*.html" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}
```

**If insights data is already in context** (Claude received it via `/insights` in this session): skip the file read and proceed directly to Step 2 using the in-context JSON.

### Step 2: Run the Extraction Script

```powershell
python "$HOME\.claude\scripts\insights-to-pdr.py" --latest
```

**What it writes:**
- `~/.agents/plans/YYYY-MM-DD-insights-<slug>.md` — one PDR per actionable item
- `~/.agents/evolve/next-session-queue.md` — queue entries appended with priority (P1/P2/P3)
- `~/.agents/audits/YYYY-MM-DD-insights-harvest-audit.md` — audit trail
- `~/.agents/learnings/YYYY-MM-DD-insights-harvest.md` — meta-brain learning

### Step 3: If Insights Data Is In-Context (No JSON File)

When `/insights` ran in this same session, Claude has the full JSON in context. In this case, write the report JSON to a temp file and feed it to the script:

```powershell
# Write in-context JSON to temp file, then process
$json = '<paste or construct JSON from context>'
$tmp = "$HOME\.claude\usage-data\report-$(Get-Date -Format 'yyyy-MM-dd-HHmmss').json"
$json | Set-Content -Path $tmp -Encoding UTF8
python "$HOME\.claude\scripts\insights-to-pdr.py" $tmp
```

**Alternative — generate PDRs directly without the script:**

If the script fails or Python is unavailable, generate PDRs directly from context using the templates in Step 4.

### Step 4: PDR Template (Manual Fallback)

For each item in `suggestions.claude_md_additions`, `suggestions.usage_patterns`, `suggestions.features_to_try`, `on_the_horizon.opportunities`:

```markdown
---
id: plan-YYYY-MM-DD-<slug>
type: plan
date: YYYY-MM-DD
goal: <title>
category: <config|workflow|feature|horizon>
priority: <P1|P2|P3>
source: insights/<section>
status: pending
---

# PDR: <title>

## Context
Sourced from `/insights` report dated YYYY-MM-DD.

## Goal
<body — extracted from insights item>

## Issues
### <SLUG>-001: Implement
**Acceptance criteria:**
- Change is applied and verified
- Learning harvested post-completion
**Dependencies:** None
```

Priority mapping:
- `suggestions.claude_md_additions` → **P1** (direct config wins, low effort)
- `suggestions.usage_patterns` → **P1** (workflow fixes, high ROI)
- `suggestions.features_to_try` → **P2** (medium effort)
- `on_the_horizon.opportunities` → **P3** (ambitious builds)

### Step 5: Verify Output

```powershell
# Confirm PDRs were written
Get-ChildItem "$HOME\.agents\plans\*insights*" | Select-Object Name, LastWriteTime

# Confirm queue updated
Select-String "Insights Harvest" "$HOME\.agents\evolve\next-session-queue.md"

# Confirm audit
Get-ChildItem "$HOME\.agents\audits\*insights*" | Select-Object Name
```

### Step 6: Schedule Weekly Autonomous Run

Wire a weekly cron via the `schedule` skill:

```
/schedule "weekly insights harvest" --cron "0 9 * * 1" --command "claude -p '/insights then /harvest-insights'"
```

Or add a SessionStart hook that runs the harvest if the last report is >7 days old:

```json
// ~/.claude/settings.json hooks.SessionStart addition:
{
  "command": "python C:\\Users\\kas41\\.claude\\scripts\\insights-harvest-check.py",
  "timeout": 10000
}
```

See `references/auto-schedule.md` for the check script.

### Step 7: Update Meta-Brain Index

After the script runs, add a pointer to the audit in `~/.claude/projects/C--Users-kas41/memory/MEMORY.md`:

```markdown
- [Insights Harvest YYYY-MM-DD](../../../.agents/audits/YYYY-MM-DD-insights-harvest-audit.md) — PDRs + queue entries from /insights run
```

## Output Structure

```
~/.agents/
  plans/
    YYYY-MM-DD-insights-config-*.md     P1 — CLAUDE.md config fixes
    YYYY-MM-DD-insights-workflow-*.md   P1 — Workflow improvements
    YYYY-MM-DD-insights-feature-*.md    P2 — Features to try
    YYYY-MM-DD-insights-horizon-*.md    P3 — Ambitious builds
  evolve/
    next-session-queue.md               Appended with P1/P2/P3 entries
  audits/
    YYYY-MM-DD-insights-harvest-audit.md
  learnings/
    YYYY-MM-DD-insights-harvest.md
```

## Key Rules

- **Always de-duplicate**: The script checks slugs before adding to the queue. Don't add items that are already queued or in an active PDR.
- **Priority is fixed**: Don't promote P3 horizon items to P1 — they're ambitious by design. Work P1s first.
- **PDRs are inputs to /rpi**: Each PDR becomes a `/rpi` invocation. The goal field maps directly to `/rpi "<goal>"`.
- **Script failure is not blocking**: If `insights-to-pdr.py` fails, use the manual template (Step 4) and continue.
- **Weekly cadence minimum**: Insights older than 14 days have diminishing ROI. Set up the schedule in Step 6.

## Examples

### Run after a fresh /insights call

```
/insights          # generates report, passes JSON to Claude in context
/harvest-insights  # Claude reads in-context JSON, writes PDRs + queue + audit
```

### Run standalone (no active /insights context)

```
/harvest-insights  # reads latest report file from usage-data/
```

### Kick off a PDR immediately

```
/rpi "fix CLAUDE.md: add workflow autonomy section"   # from P1 PDR
```

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `No insights reports found` | No report files in usage-data/ | Run `/insights` first, then re-run |
| `bd: no database found` | bd CLI broken | Fallback: `next-session-queue.md` is always used |
| `Python not found` | Python not on PATH | Use manual PDR template (Step 4) |
| PDRs duplicated after re-run | Slug check missed | Check `<!-- slug:... -->` comments in queue file |
| Queue file missing | First run or deleted | Script creates it automatically |

## See Also

- `skills/rpi/SKILL.md` — PDRs feed directly into RPI lifecycle
- `skills/harvest/SKILL.md` — General transcript harvesting (different from insights harvest)
- `skills/forge/SKILL.md` — Promotes knowledge artifacts from pending to active
- `~/.claude/scripts/insights-to-pdr.py` — The extraction engine
