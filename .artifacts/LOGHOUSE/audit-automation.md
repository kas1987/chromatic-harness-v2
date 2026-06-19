# LOGHOUSE Audit Automation
**Automated weekly audit report generation with zero manual work and continuous anomaly detection**

---

## Overview

Two audit generators are available:

1. **Shell Script** (`~/.claude/bin/audit-loghouse-weekly.sh`)
   - Native bash/sh for Unix/Linux/WSL
   - Direct file manipulation
   - Cron-compatible

2. **Node.js API** (`~/.claude/bin/audit-loghouse-api.js`)
   - Cross-platform (Windows, Mac, Linux)
   - JSON/Markdown/CSV output
   - Integrates with LOGHOUSE server

Both are scheduled to run **every Friday 18:00 UTC**.

---

## Setup Instructions

### Option 1: Unix/Linux/WSL (Bash Cron)

**1. Make script executable:**
```bash
chmod +x ~/.claude/bin/audit-loghouse-weekly.sh
```

**2. Add cron job:**
```bash
# Open crontab editor
crontab -e

# Add this line (Friday 18:00 UTC):
0 18 * * 5 /home/kas41/.claude/bin/audit-loghouse-weekly.sh >> ~/.claude/bin/audit-loghouse.log 2>&1
```

**3. Verify:**
```bash
crontab -l | grep audit-loghouse
```

### Option 2: Windows (Task Scheduler)

**1. Create scheduled task:**
```powershell
# Run as Administrator
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At 6:00PM -UTC
$action = New-ScheduledTaskAction -Execute "C:\Program Files\nodejs\node.exe" `
  -Argument "$env:USERPROFILE\.claude\bin\audit-loghouse-api.js --markdown --save"
Register-ScheduledTask -TaskName "LOGHOUSE Weekly Audit" -Trigger $trigger -Action $action -User $env:USERNAME -RunLevel Highest
```

**2. Verify:**
```powershell
Get-ScheduledTask | Where-Object {$_.TaskName -eq "LOGHOUSE Weekly Audit"} | Select-Object State, Triggers
```

### Option 3: Claude Code Hook

**Add to `~/.claude/settings.json`:**
```json
{
  "hooks": {
    "PostCompact": "/home/kas41/.claude/bin/audit-loghouse-api.js --markdown --save"
  }
}
```

This runs the audit after context compaction (roughly weekly for active users).

---

## Alert Thresholds

Configure via environment variables:

```bash
# Shell script
export DAILY_TOOLS_THRESHOLD=4000       # Tools/day alert
export PEAK_HOUR_THRESHOLD=1500         # Tools/hour alert
export SUSTAINED_RATE_THRESHOLD=350     # Sustained rate alert
export TASK_TRACKING_MIN=0.5            # Min task tracking %
export AGENT_USAGE_MIN=10               # Min agent usage %

# Then run
~/.claude/bin/audit-loghouse-weekly.sh
```

**Or edit defaults in script:**
```bash
# In audit-loghouse-weekly.sh, line ~20
DAILY_TOOLS_THRESHOLD=4000
PEAK_HOUR_THRESHOLD=1500
SUSTAINED_RATE_THRESHOLD=350
TASK_TRACKING_MIN=0.5
AGENT_USAGE_MIN=10
```

**Default Thresholds (from baseline):**
| Threshold | Value | Rationale |
|-----------|-------|-----------|
| Daily Tools | 4,000 | 1.4x baseline (2,935) |
| Peak Hour | 1,500 | 6.4x baseline (234) |
| Sustained Rate | 350 | 1.5x baseline (234) |
| Task Tracking | 0.5% | Below current 0.8%, trigger review |
| Agent Usage | 10% | Improvement target from current 0.7% |

---

## Manual Execution

### Run Audit Now (Any Format)

**Markdown (default):**
```bash
node ~/.claude/bin/audit-loghouse-api.js --markdown
```

**JSON (for API integration):**
```bash
node ~/.claude/bin/audit-loghouse-api.js --json
```

**CSV (for spreadsheets):**
```bash
node ~/.claude/bin/audit-loghouse-api.js --csv
```

**Save to LOGHOUSE:**
```bash
node ~/.claude/bin/audit-loghouse-api.js --markdown --save
```

### Shell Script (Unix/Linux/WSL)

```bash
~/.claude/bin/audit-loghouse-weekly.sh
```

**With custom thresholds:**
```bash
DAILY_TOOLS_THRESHOLD=5000 AGENT_USAGE_MIN=5 \
  ~/.claude/bin/audit-loghouse-weekly.sh
```

---

## Output Locations

Reports are saved to:
```
chromatic-harness-v2/.artifacts/LOGHOUSE/
├── audits/
│   └── YYYY-MM-DD-weekly-summary.md
├── alerts/
│   └── YYYY-MM-DD-alerts.json
└── audit-history.log
```

**audit-history.log:**
```
[2026-06-19T18:00:00Z] Audit complete: .../audits/2026-06-19-weekly-summary.md (0 alerts)
[2026-06-26T18:00:00Z] Audit complete: .../audits/2026-06-26-weekly-summary.md (2 alerts)
```

---

## Alert Handling

### Alert Types

| Type | Threshold | Action |
|------|-----------|--------|
| `HIGH_DAILY_TOOLS` | Tools > 4,000 | Review dashboard, check for anomalies |
| `LOW_AGENT_USAGE` | Agent % < 10% | Consider parallelization opportunities |
| `LOW_ACTIVITY` | Tools < 500 | Normal for light weeks |
| `PEAK_HOUR_SPIKE` | Peak hour > 1,500 | Load balance analysis recommended |

### Alert JSON Format

```json
{
  "timestamp": "2026-06-19T18:00:00Z",
  "alerts": [
    {
      "type": "HIGH_DAILY_TOOLS",
      "message": "Daily tools (4606) exceeds threshold (4000)",
      "severity": "warning"
    }
  ]
}
```

### Respond to Alerts

1. **Check LOGHOUSE Dashboard:** http://localhost:3333/api/audits/latest
2. **Review Alert Details:** `.artifacts/LOGHOUSE/alerts/YYYY-MM-DD-alerts.json`
3. **View Correlation:** Check git history for that period
4. **Update Thresholds:** If alert is false positive, adjust via environment variables
5. **Archive Alert:** Move to `.artifacts/LOGHOUSE/alerts/ARCHIVE/` when resolved

---

## Integration with LOGHOUSE Server

The audit data feeds into the LOGHOUSE server:

```
audit-loghouse-weekly.sh → .artifacts/LOGHOUSE/audits/*.md
                               ↓
                        LOGHOUSE Server (port 3333)
                               ↓
                        Dashboard + API
```

**Access via API:**
```bash
# Get latest audit
curl http://localhost:3333/api/audits/latest

# List all audits
curl http://localhost:3333/api/audits/reports

# Search
curl "http://localhost:3333/api/audits/search?q=HIGH"
```

---

## Enabling/Disabling

### Disable Cron (Unix/Linux/WSL)
```bash
# Remove from crontab
crontab -e
# Delete the audit-loghouse line
```

### Disable Task Scheduler (Windows)
```powershell
Disable-ScheduledTask -TaskName "LOGHOUSE Weekly Audit"
```

### Disable Hook (Claude Code)
```bash
# Edit ~/.claude/settings.json
# Remove PostCompact hook or set to empty
```

### Re-enable
Simply reverse the steps above, or manually run:
```bash
node ~/.claude/bin/audit-loghouse-api.js --markdown --save
```

---

## Troubleshooting

### "audit.log not found"
**Issue:** Script can't find ~/.claude/audit.log
**Solution:** Verify audit logging is enabled in Claude Code. See `LOGHOUSE/README.md` for audit log setup.

### "No audit data"
**Issue:** audit.log exists but is empty
**Solution:** Run at least one Claude Code session first to populate audit.log

### "Cron job not running"
**Issue:** Task is scheduled but not executing
**Solution:**
```bash
# Check cron logs
grep CRON /var/log/syslog  # Linux
log show --predicate 'eventMessage contains[cd] "cron"'  # macOS

# Run manually to test
~/.claude/bin/audit-loghouse-weekly.sh

# Check permissions
ls -l ~/.claude/bin/audit-loghouse-weekly.sh
# Should be: -rwxr-xr-x
```

### "Node: command not found"
**Issue:** Node.js not in PATH for scheduled task
**Solution:** Use full path to node:
```bash
# Find node path
which node
# Use full path in cron/task scheduler
/usr/local/bin/node ~/.claude/bin/audit-loghouse-api.js --markdown --save
```

### Alerts not saving
**Issue:** Alerts not written to `.artifacts/LOGHOUSE/alerts/`
**Solution:** Check directory permissions:
```bash
mkdir -p ~/.claude/../chromatic-harness-v2/.artifacts/LOGHOUSE/alerts
chmod 755 ~/.claude/../chromatic-harness-v2/.artifacts/LOGHOUSE/alerts
```

---

## Advanced Usage

### Dry Run (No Write)
```bash
# Just output, don't save
node ~/.claude/bin/audit-loghouse-api.js --markdown

# Inspect what would be saved
node ~/.claude/bin/audit-loghouse-api.js --json | jq .alerts
```

### Custom Alert Thresholds Per Run
```bash
DAILY_TOOLS_THRESHOLD=6000 \
AGENT_USAGE_MIN=15 \
  node ~/.claude/bin/audit-loghouse-api.js --markdown --save
```

### Export All Reports
```bash
cd chromatic-harness-v2/.artifacts/LOGHOUSE/audits/
# Create CSV index
for f in *.md; do echo "$f"; done | sort > index.txt

# Backup to archive
tar czf archive-$(date +%Y-%m-%d).tar.gz *.md alerts/
```

### Parse Report for Specific Metric
```bash
# Extract tool count from latest report
grep "Total Tools" chromatic-harness-v2/.artifacts/LOGHOUSE/audits/*-weekly-summary.md | tail -1
```

---

## Performance

- **Execution time:** ~2-5 seconds (shell) or ~3-8 seconds (Node.js)
- **File I/O:** Reads audit.log once, writes one report + alert JSON
- **CPU:** Minimal (text parsing, no compute)
- **Storage:** ~50 KB per report, ~10 KB per alert

**Storage projections:**
- Weekly reports: 52 reports/year = 2.6 MB/year
- Alerts (avg 2 per week): 104 alerts/year = 1 MB/year
- **Total:** ~3.6 MB/year

Archive annually to `.artifacts/LOGHOUSE/archive/` to maintain performance.

---

## See Also

- `LOGHOUSE/README.md` — Full server documentation
- `LOGHOUSE/audits/` — Generated reports
- `LOGHOUSE/alerts/` — Alert history
- `~/.claude/audit.log` — Raw audit data
- `LOGHOUSE_SERVER/` — Dashboard and API server

---

**Last Updated:** 2026-06-19  
**Status:** ✅ Ready for deployment  
**Next Audit:** Friday 18:00 UTC (automated)
