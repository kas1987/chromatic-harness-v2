# Git State Snapshots & Last-Known-Good Flow (OBS-006)

Three scripts capture and gate on git working-tree state so agent work is
recoverable and incidents can point at a precise repo state.

## Scripts

### `snapshot_git_state.py`
Captures `branch`, `commit`, `dirty`, and a `changed_files` breakdown
(`staged` / `modified` / `untracked`, parsed from `git status --porcelain`).

```bash
python scripts/snapshot_git_state.py                      # -> .chromatic/last_known_good.json
python scripts/snapshot_git_state.py --out .chromatic/pre_work.json
```

It also writes a stable pointer at `.chromatic/latest_snapshot.json` (including
a `snapshot_path` field) so **incident records can always reference the latest
snapshot** without knowing the per-run filename.

### `check_dirty_state.py`
Reports dirty state. Advisory by default (exit 0); `--strict` turns it into a
hard gate (exit 1 when dirty) for pre/post-work enforcement.

```bash
python scripts/check_dirty_state.py            # advisory: always exit 0
python scripts/check_dirty_state.py --strict   # gate: exit 1 if dirty
```

### `update_last_known_good.py`
Records a **validated clean** checkpoint. Refuses to write when the tree is
dirty unless `--force` is given; stamps `validated` / `forced` flags.

```bash
python scripts/update_last_known_good.py           # only records if clean
python scripts/update_last_known_good.py --force   # records dirty, validated=false
```

## Before/after agent-work flow

```bash
# Before work: capture a baseline.
python scripts/snapshot_git_state.py --out .chromatic/pre_work.json

# ... agent does work ...

# After work: gate on cleanliness, then promote a checkpoint.
python scripts/check_dirty_state.py --strict && \
  python scripts/update_last_known_good.py
```

## Incident linking

When routing an incident, reference `.chromatic/latest_snapshot.json` to record
exactly which branch/commit/dirty-state the harness was in when the event fired.
The pointer's `snapshot_path` field locates the full per-run snapshot.
