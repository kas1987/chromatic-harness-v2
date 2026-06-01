# Agent Mission Packet: Observability Required

## Required Before Work

1. Read the task objective and allowed files.
2. Claim every file you intend to mutate:

```bash
python scripts/claim_files.py --writer <agent> --session <session_id> --task <task_id> --files <paths>
```

3. Snapshot Git state if the task is medium risk or higher:

```bash
python scripts/snapshot_git_state.py --out .chromatic/last_known_good.json
```

## Required During Work

- Use `harness_run.py` for build/test/lint commands where possible.
- Log any failure at medium severity or higher.
- Halt if a file claim is blocked.
- Do not override another writer without human approval.

## Required After Work

1. Validate logs.
2. Release claimed files.
3. Generate or update a report when requested.
