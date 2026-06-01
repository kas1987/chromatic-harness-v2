# Quickstart

## 1. Copy Bundle Into Repo

Copy all files into the target repo root.

## 2. Log Bootstrap Event

```bash
python scripts/log_harness_event.py \
  --source terminal \
  --event-type info \
  --severity info \
  --category manual_note \
  --message "Observability bundle installed" \
  --status resolved
```

## 3. Validate Event Log

`validate_event_schema.py` is the **required** validator (used by CI): it enforces
the full event schema — required fields, `source.surface`, and the `severity`,
`event_type`, `category`, and `status` enums — and exits non-zero on any malformed
line or out-of-schema value.

```bash
python scripts/validate_event_schema.py --log 00_META/observability/ERROR_LOG.jsonl
```

## 4. Detect Collisions

```bash
python scripts/detect_file_collisions.py --active-writers .chromatic/active_writers.json
```

## 5. Summarize Patterns

```bash
python scripts/summarize_error_patterns.py --log 00_META/observability/ERROR_LOG.jsonl
```
