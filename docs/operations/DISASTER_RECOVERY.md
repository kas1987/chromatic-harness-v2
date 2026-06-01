# Disaster Recovery Playbook — chromatic-harness-v2 (GH #88)

## RTO / RPO Targets

| Target | Value | Definition |
|--------|-------|-----------|
| **RTO** | 4 hours | Harness fully operational from incident declaration |
| **RPO** | 24 hours | Maximum acceptable data loss |

## Critical State Locations

| Priority | Path | Description | Recovery Note |
|----------|------|-------------|---------------|
| P1 | `.beads/` | Beads issue tracker (local Dolt DB + JSONL export) | Restore from backup; run `bd dolt pull` to sync remote |
| P1 | `.agents/` | Agent handoffs, plans, council, harvest, swarm results | Restore from backup; re-run `python scripts/session_start.py` |
| P1 | `00_SOURCE_OF_TRUTH/` | Canon registry, governance truth artifacts | Restore from git history or backup snapshot |
| P1 | `.claude/settings.json` | Claude harness settings (hooks, env vars, permissions) | Restore from backup — never commit tokens, redact first |
| P2 | `07_LOGS_AND_AUDIT/` | Telemetry, budget ledger, audit trails, security scans | Restore from backup; historical logs not required for operation |
| P2 | `01_STATE/` | Agent handoff queue, session state | Restore from git or backup; reconstruct queue from beads if lost |
| P2 | `02_RUNTIME/` | Runtime engines, router config, roach-pi submodule | Restore from git checkout + submodule update |
| P3 | `config/` | Pre-session inventory, config snapshots | Regenerate: `python scripts/generate_pre_session_inventory.py` |

## Tooling

All DR operations are driven by `scripts/disaster_recovery.py`.

```bash
# Scan and inventory critical state (generates dr_inventory.json)
python scripts/disaster_recovery.py --inventory

# Create timestamped backup snapshot
python scripts/disaster_recovery.py --backup --dest /path/to/backup

# Print the restore procedure
python scripts/disaster_recovery.py --restore

# JSON output for any mode
python scripts/disaster_recovery.py --inventory --json
```

The inventory is written to `07_LOGS_AND_AUDIT/operations/dr_inventory.json`.

## Restore Procedure

> DO NOT run automated restores without first understanding the current repo state.

### Step 1 — Verify Git State

```bash
git status
git log --oneline -5
# Confirm you are on the correct branch/commit.
```

### Step 2 — Restore P1 Critical State

```bash
BACKUP_ROOT=/path/to/backup/chromatic-harness-backup-<TIMESTAMP>

# Beads issue tracker
cp -r $BACKUP_ROOT/.beads/ ./.beads/
bd dolt pull                   # sync Dolt remote

# Agent state
cp -r $BACKUP_ROOT/.agents/ ./.agents/

# Source of truth
cp -r $BACKUP_ROOT/00_SOURCE_OF_TRUTH/ ./00_SOURCE_OF_TRUTH/

# Claude settings (REMOVE SECRETS BEFORE COMMITTING)
cp $BACKUP_ROOT/.claude/settings.json ./.claude/settings.json
```

### Step 3 — Restore P2 State

```bash
cp -r $BACKUP_ROOT/07_LOGS_AND_AUDIT/ ./07_LOGS_AND_AUDIT/
cp -r $BACKUP_ROOT/01_STATE/ ./01_STATE/
cp -r $BACKUP_ROOT/02_RUNTIME/ ./02_RUNTIME/
```

### Step 4 — Restore Runtime Submodule

```bash
git submodule update --init --recursive
```

### Step 5 — Validate Harness Health

```bash
python scripts/harness_health_check.py
python scripts/validate_claude_harness.py --machine
```

### Step 6 — Regenerate Derived State

```bash
python scripts/generate_pre_session_inventory.py
python scripts/session_start.py
```

### Step 7 — Verify Beads Sync

```bash
bd ready
bd dolt push
```

## Backup Automation

To create a backup snapshot:

```bash
# Default destination: /tmp/chromatic-dr-backups
python scripts/disaster_recovery.py --backup

# Custom destination
python scripts/disaster_recovery.py --backup --dest /your/backup/path

# Set via env var
export DR_BACKUP_DEST=/your/backup/path
python scripts/disaster_recovery.py --backup
```

The backup creates a `chromatic-harness-backup-<TIMESTAMP>/` directory containing all
P1–P3 critical paths and a `MANIFEST.json` listing every copied item and its status.

## Inventory Schema

`07_LOGS_AND_AUDIT/operations/dr_inventory.json` follows schema `dr_inventory_v1`:

```json
{
  "schema": "dr_inventory_v1",
  "timestamp": "2026-06-01T00:00:00Z",
  "repo": "/path/to/repo",
  "rto_hours": 4,
  "rpo_hours": 24,
  "total_critical_bytes": 12345678,
  "total_critical_human": "11.8 MB",
  "items": [
    {
      "path": ".beads",
      "description": "Beads issue tracker (local Dolt DB + JSONL export)",
      "priority": "P1",
      "exists": true,
      "size_bytes": 8192000,
      "size_human": "7.8 MB",
      "last_modified": "2026-06-01T12:00:00+00:00",
      "recovery_note": "..."
    }
  ]
}
```

## Incident Response Checklist

- [ ] Declare incident; note timestamp
- [ ] Run `python scripts/disaster_recovery.py --inventory` — assess what is intact
- [ ] Identify most recent backup snapshot from `DR_BACKUP_DEST`
- [ ] Restore P1 paths first (beads, agents, source-of-truth, settings)
- [ ] Restore P2 paths (logs, state, runtime)
- [ ] Run harness health check
- [ ] Regenerate derived state
- [ ] Verify beads sync
- [ ] Declare recovery complete; note elapsed time vs RTO (4h target)
