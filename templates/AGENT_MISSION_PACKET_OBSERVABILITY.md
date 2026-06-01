# Agent Mission Packet: Observability Required

## Required Before Work

1. **Read the task objective and allowed files.**
2. **Claim every file you intend to mutate:**

```bash
python scripts/claim_files.py --writer <agent> --session <session_id> --task <task_id> --files <paths>
```

3. **Snapshot Git state if the task is medium risk or higher:**

```bash
python scripts/snapshot_git_state.py --out .chromatic/last_known_good.json
```

4. **Check for dirty repo state** that could create ambiguity:

```bash
python scripts/check_dirty_state.py
```

## Required During Work

- **Use `harness_run.py` for build/test/lint commands** where possible:

```bash
python scripts/harness_run.py -- npm test
python scripts/harness_run.py -- ruff check .
```

- **Log any failure at medium severity or higher** to `00_META/observability/ERROR_LOG.jsonl`.
- **Halt immediately if a file claim is blocked** — do not override another writer without human approval.
- **Run `scan_for_secrets.py` before committing** if you touched files that might contain credentials:

```bash
python scripts/scan_for_secrets.py --paths <files>
```

- **Validate event schema** when generating structured events:

```bash
python scripts/validate_event_schema.py --record <json-file>
```

## Required After Work

1. **Validate logs:** ensure all events you generated are schema-valid and severity-appropriate.
2. **Release claimed files:**

```bash
python scripts/release_files.py --writer <agent> --files <paths>
```

3. **Generate or update a report** when requested:

```bash
python scripts/generate_observability_report.py --since <iso-date>
```

## Stop Conditions — Halt and Escalate

| Condition | Signal | Action |
|---|---|---|
| **Collision** | File claim blocked or `detect_file_collisions.py` flags overlap | Halt. Do not write. Escalate to orchestrator. |
| **Dirty repo ambiguity** | `check_dirty_state.py` reports uncommitted changes outside allowed scope | Halt. Snapshot and clarify scope before continuing. |
| **Schema validation failure** | `validate_event_schema.py` rejects an event you generated | Halt. Fix the record. Do not append invalid events. |
| **Secret detection** | `scan_for_secrets.py` or `redact_secrets.py` flags exposure in a committed/shared log | Halt immediately. Open critical incident. Do NOT commit. |
| **Blocked claim override** | Another agent holds a claim on a file you need to mutate | Halt. Request human approval before overriding. |
| **Unexpected test failure outside touched scope** | `harness_run.py` logs a failure in files you did not modify | Halt. Create follow-up queue item. Do not mask. |

## Acceptance Criteria Checklist

Before marking work complete:

- [ ] All mutated files were claimed before mutation.
- [ ] All claimed files are released after mutation.
- [ ] Git state was snapshotted for medium-or-higher risk tasks.
- [ ] No secrets were exposed in committed or shared output.
- [ ] All generated events pass schema validation.
- [ ] Stop conditions were respected; any halts are documented.
- [ ] Observability logs link to the task ID and agent name.
