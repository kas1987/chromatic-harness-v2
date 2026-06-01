# Event Lifecycle & Archive Policy (OBS-011)

The event log `00_META/observability/ERROR_LOG.jsonl` is an **append-only**
history. Events are never edited or deleted in place; status changes are
recorded as additional records.

## Tools

### `find_event.py`
Locate an event by id. Prints the latest record by default; `--history` shows
the full lifecycle.

```bash
python scripts/find_event.py --event-id evt_20260601_120000_ab12cd
python scripts/find_event.py --event-id evt_... --history
```

### `update_event_status.py`
Append a `status_update` record. **Append-only** — it never mutates the
original line. The new record carries the **same `event_id`** (with a later
timestamp), plus `previous_status` and `updates_event` fields, so reports can
group an event with all its updates.

```bash
python scripts/update_event_status.py --event-id evt_... --status resolved \
  --linked-fix PR#152 --note "fixed by reformat"
```

Allowed statuses: `open, routed, queued, active, resolved, ignored, failed,
incident_opened, collision_opened`.

## Latest-status semantics

Because lifecycle records share an `event_id`, the report
(`generate_observability_report.py`) computes **latest status per event_id** by
taking the most recent record by timestamp. A `resolved` update therefore moves
an event out of the "Unresolved High/Critical" and "Open/Routed" sections
without rewriting history.

## Archive policy

The log grows monotonically. To keep it manageable while preserving history:

1. **Rotate by period.** When `ERROR_LOG.jsonl` grows large (e.g. monthly, or
   past ~50 MB), move it to
   `00_META/observability/archive/ERROR_LOG_<YYYY-MM>.jsonl` and start a fresh
   active log. Never edit archived files.
2. **Archive only fully-resolved events.** An event is eligible for archival
   once its latest status is `resolved` or `ignored`. Keep open/unresolved
   events in the active log so reports still surface them.
3. **Append-only guarantee holds across archives.** Archives are immutable;
   corrections are new appended records, not edits.
4. **Index archives.** Keep `00_META/observability/archive/INDEX.md` listing
   each archive file, its period, and event count, so `find_event.py` users
   know where to look for old ids.
5. **Retention.** Retain archives per the project's audit-retention policy;
   do not delete without an explicit retention decision (audit trail).
