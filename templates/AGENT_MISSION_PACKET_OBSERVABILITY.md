# Agent Mission Packet: Observability Required

Every dispatched agent MUST follow this packet. It defines the observability
actions required **before**, **during**, and **after** work, the **stop
conditions** that force a safe halt, and the **definition of done** (which
requires releasing all claimed files).

## Required Before Work

1. Read the task objective and the allowed-files list.
2. **Claim every file you intend to mutate** (file claims are mandatory before
   any mutation — an unclaimed write is a protocol violation):

   ```bash
   python scripts/claim_files.py --writer <agent> --session <session_id> --task <task_id> --files <paths>
   ```

   If the claim is blocked, STOP (see Stop Conditions).

3. Snapshot Git state for medium-risk-or-higher tasks:

   ```bash
   python scripts/snapshot_git_state.py --out .chromatic/last_known_good.json
   ```

4. Confirm a clean starting point:

   ```bash
   python scripts/check_dirty_state.py        # advisory; investigate surprises
   ```

## Required During Work

- Run build/test/lint via the wrapper so failures are logged + routed:

  ```bash
  python scripts/harness_run.py --route -- <command>
  ```

- Log any failure at **medium severity or higher**.
- Do not override another writer's claim without explicit human approval.
- Re-snapshot before destructive operations.

## Stop Conditions (halt and escalate)

Halt immediately, do not mutate further, and escalate to a human/auditor if ANY
of these occur:

1. **File-claim collision** — a claim is blocked / another active writer holds a
   target file:

   ```bash
   python scripts/detect_file_collisions.py --active-writers .chromatic/active_writers.json
   ```

2. **Dirty-repo ambiguity** — unexpected uncommitted changes you did not make
   (you cannot attribute the working-tree state):

   ```bash
   python scripts/check_dirty_state.py --strict   # non-zero => stop
   ```

3. **Schema validation failure** — the event log fails schema validation:

   ```bash
   python scripts/validate_event_schema.py --log 00_META/observability/ERROR_LOG.jsonl
   ```

4. **Secret detection** — a secret is detected in staged changes:

   ```bash
   python scripts/scan_for_secrets.py --staged   # non-zero => stop, do not commit
   ```

When stopped, record the reason as an event (`severity: high`) and route it.

## Required After Work

1. Validate logs:

   ```bash
   python scripts/validate_event_schema.py --log 00_META/observability/ERROR_LOG.jsonl
   ```

2. **Release every claimed file** (see Definition of Done):

   ```bash
   python scripts/release_files.py --writer <agent> --session <session_id> --files <paths>
   ```

3. Generate or update a report when requested:

   ```bash
   python scripts/generate_observability_report.py
   ```

## Definition of Done (acceptance criteria)

A task is NOT complete until all of the following hold:

- [ ] Every mutated file was **claimed before** mutation.
- [ ] No open Stop Condition remains (no unresolved collision, no unexplained
      dirty state, schema validation passes, no detected secret).
- [ ] The event log validates against the schema.
- [ ] **All claimed files have been released** (`release_files.py`) — leaving a
      claim held blocks other agents and fails acceptance.
- [ ] Failures encountered were logged (and routed if medium+).
