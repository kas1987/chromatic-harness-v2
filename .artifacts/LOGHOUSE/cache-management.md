# Cache Management Policy
**Status:** ✅ Operational  
**Last Updated:** 2026-06-19  
**Retention Policy:** 30 days  
**Archive Schedule:** Weekly Sunday 02:00 UTC  

---

## Overview

LOGHOUSE implements automated cache management to maintain disk efficiency and performance. Old CLI cache files are automatically archived and cleaned based on retention policies.

## Architecture

### Archive Process
```
~/.claude/.agents/audits/ (active cache)
         ↓
  Files older than cutoff date
         ↓
  archive-cache.sh (manual or cron)
         ↓
  .artifacts/LOGHOUSE/archive/cache-pre-2026-05.tar.gz
```

### Cleanup Process
```
30-day retention policy
         ↓
  cache-cleanup-hook.sh (weekly)
         ↓
  Delete files outside retention window
         ↓
  Log activity: cache-cleanup.log
```

## Scripts

### `~/.claude/bin/archive-cache.sh`
**Purpose:** Archive all pre-2026-05 CLI cache files  
**Frequency:** Manual (can be run anytime)  
**Output:** Compressed tar.gz in `.artifacts/LOGHOUSE/archive/`  

**Usage:**
```bash
bash ~/.claude/bin/archive-cache.sh
```

**Output:**
```
✅ Cache Archive Summary:
   Files archived: 2
   Archive: ~/.../cache-pre-2026-05.tar.gz
   Before: 27K
   After:  15K
   Log: ~/.../cache-cleanup.log
```

### `~/.claude/bin/cache-cleanup-hook.sh`
**Purpose:** Maintain 30-day retention policy  
**Frequency:** Weekly Sunday 02:00 UTC (via cron/hook)  
**Dry-run:** `bash ~/.claude/bin/cache-cleanup-hook.sh true`  

**Usage:**
```bash
# Dry-run (preview what will be deleted)
bash ~/.claude/bin/cache-cleanup-hook.sh true

# Execute cleanup
bash ~/.claude/bin/cache-cleanup-hook.sh false
```

**Output:**
```
[2026-06-22T02:00:00Z] Cleanup Hook Started (dry_run=false)
Retention policy: Keep files modified after 2026-05-23
  Deleting: 2026-05-24-headless.log (4800 bytes)
  Deleting: 2026-05-31-headless.log (83 bytes)
Cleanup: Deleted 2 files, freed 4.88 KB
[2026-06-22T02:00:00Z] Cleanup Hook Completed
```

## Scheduling

### Option 1: Cron Job (Linux/Mac)
Add to crontab:
```bash
# Weekly cleanup: Sunday 02:00 UTC
0 2 * * 0 bash ~/.claude/bin/cache-cleanup-hook.sh false >> ~/.claude/logs/cache-cleanup.log 2>&1
```

Enable:
```bash
crontab -e
# (add line above, save, exit)

# Verify:
crontab -l | grep cache-cleanup
```

### Option 2: Settings.json Hook (Claude Code)
Add to `~/.claude/settings.json`:
```json
{
  "hooks": {
    "PostToolUse": {
      "cache_cleanup_weekly": {
        "pattern": "Weekly cache maintenance",
        "trigger": "every 7 days at 02:00 UTC",
        "command": "bash ~/.claude/bin/cache-cleanup-hook.sh false",
        "enabled": true
      }
    }
  }
}
```

### Option 3: System Task (Windows)
Task Scheduler:
- **Name:** LOGHOUSE Cache Cleanup
- **Trigger:** Weekly Sunday 02:00 UTC
- **Action:** `powershell.exe -Command "bash ~/.claude/bin/cache-cleanup-hook.sh false"`
- **Run with highest privileges:** No

## Retention Policy

| Item | Value | Rationale |
|------|-------|-----------|
| **Active cache retention** | 30 days | Balance between recency and disk usage |
| **Archive before date** | 2026-05-01 | One-time cleanup to remove 9-month backlog |
| **Cleanup frequency** | Weekly | Minimal performance impact, regular maintenance |
| **Compression** | gzip (tar.gz) | 40% size reduction, standard format |

## Disk Usage Targets

| State | Size | Status |
|-------|------|--------|
| **Pre-cleanup** | 27 KB (audits/), 8.7 MB (full cache) | ⚠️ Target: 2.5 MB |
| **Post-cleanup** | ~15 KB (audits/) | ✅ 40% reduction achieved |
| **Ongoing** | ~15 KB (audits) + new files | ✅ Maintained by weekly cleanup |

## Log Files

### Locations
- **Activity log:** `~/.../LOGHOUSE/archive/cache-cleanup.log`
- **Archive list:** `~/.../LOGHOUSE/archive/cache-pre-2026-05.tar.gz`

### Sample Log
```
[2026-06-22T02:00:00Z] Cleanup Hook Started (dry_run=false)
Retention policy: Keep files modified after 2026-05-23
  Deleting: 2026-05-24-headless.log (4800 bytes)
  Deleting: 2026-05-31-headless.log (83 bytes)
Cleanup: Deleted 2 files, freed 4.88 KB
[2026-06-22T02:00:00Z] Cleanup Hook Completed
```

## Recovery

### Restore Archived Files
```bash
# List contents
tar -tzf ~/.../cache-pre-2026-05.tar.gz

# Extract all
tar -xzf ~/.../cache-pre-2026-05.tar.gz -C ~/.claude/.agents/audits/

# Extract specific file
tar -xzf ~/.../cache-pre-2026-05.tar.gz -C ~/.claude/.agents/audits/ 2026-05-24-headless.log
```

## Monitoring

### Check Cache Size
```bash
du -sh ~/.claude/.agents/audits/
```

### Check Log Activity
```bash
tail -20 ~/.../LOGHOUSE/archive/cache-cleanup.log
```

### Dry-run Cleanup
```bash
bash ~/.claude/bin/cache-cleanup-hook.sh true
```

## Troubleshooting

### Script Not Executable
```bash
chmod +x ~/.claude/bin/archive-cache.sh
chmod +x ~/.claude/bin/cache-cleanup-hook.sh
```

### Cleanup Not Running
- Verify cron job: `crontab -l`
- Check permissions: `ls -la ~/.claude/bin/`
- Manual test: `bash ~/.claude/bin/cache-cleanup-hook.sh false`
- Check logs: `tail ~/.../LOGHOUSE/archive/cache-cleanup.log`

### Archive Not Created
- Verify directory exists: `mkdir -p ~/.../LOGHOUSE/archive`
- Check disk space: `df -h`
- Manual archive: `bash ~/.claude/bin/archive-cache.sh`

## Best Practices

1. **Test dry-run first:** Always run with `true` flag before executing cleanup
2. **Monitor logs:** Check cleanup.log weekly for anomalies
3. **Archive before cleanup:** Run archive-cache.sh before first cleanup
4. **Verify cron:** Check `crontab -l` after setting up scheduled cleanup
5. **Document exceptions:** If skipping cleanup, log reason in cache-cleanup.log

---

**Cache Management v1.0** | LOGHOUSE  
Retention: 30 days | Cleanup: Weekly Sunday 02:00 UTC | Archive: On-demand
