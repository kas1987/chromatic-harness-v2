# Event Archive Policy

## Purpose

Define how Chromatic Harness observability JSONL event logs are archived, rotated, and retained to prevent unbounded growth while preserving auditability.

## Scope

Applies to all JSONL event logs under `00_META/observability/` and `07_LOGS_AND_AUDIT/`.

## Archive Rules

### 1. Retention Tiers

| Tier | Log Type | Hot Retention | Archive After | Final Purge After |
|---|---|---|---|---|
| A | ERROR_LOG.jsonl (active) | 90 days | compress + move to archive/ | 2 years |
| B | Resolution/dispatch logs | 30 days | compress + move to archive/ | 1 year |
| C | reviewer_patterns.jsonl | 180 days | compress + move to archive/ | 3 years |
| D | Security scans | 365 days | compress + move to archive/ | 5 years |

### 2. Hot-to-Archive Transition

When a log exceeds its hot retention:

1. Rotate the JSONL file: `ERROR_LOG.jsonl` → `ERROR_LOG_YYYY-MM.jsonl.gz`
2. Move to `00_META/observability/archive/`
3. Seed a new empty JSONL file
4. Append a rotation marker event to the new file

### 3. Compression

- gzip at level 6
- Preserve original filename + `.gz` suffix
- Keep the last 90 days uncompressed for fast tail queries

### 4. Querying Archived Events

Use `find_event.py` against the hot log only. For historical lookup:

```bash
zcat 00_META/observability/archive/ERROR_LOG_2026-06.jsonl.gz | \
  python scripts/find_event.py --event-id evt_xxx
```

### 5. Append-Only Guarantee

Event logs must never be edited in-place. Status changes are handled by:

1. Appending a `status_update` event with the same `event_id`
2. Reports compute latest status from the most recent event per `event_id`
3. Archives preserve the full append-only chain for audit

### 6. Safe False-Positive Handling

Lines containing `pragma: allowlist secret` are skipped by the secret scanner. This is the only supported allowlist mechanism. Never disable entire rules.

## Responsibilities

- **Archivist**: maintains archive policy docs and rotation schedules
- **Sentinel**: reviews security scan archives before purge
- **Auditor**: verifies append-only integrity with `log_integrity_check.py`
