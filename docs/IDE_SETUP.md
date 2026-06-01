# IDE Setup — Observability Tasks (OBS-007)

The harness ships VS Code / Cursor / Antigravity **tasks** so observability
actions are one command away. They live in [`.vscode/tasks.json`](../.vscode/tasks.json)
and run through the editor's Task Runner — no extension required.

## Running a task

- **VS Code / Cursor / Antigravity:** `Ctrl/Cmd+Shift+P` → **Tasks: Run Task** →
  pick a task below.
- **Keyboard:** bind a key to `workbench.action.tasks.runTask` for faster access.
- **Terminal equivalent:** every task is a plain `python scripts/…` call, so you
  can run the same command directly in any shell.

## Observability tasks

| Task | Script | What it does |
|---|---|---|
| **Observability: Validate event logs** | `validate_event_schema.py` | Validate `00_META/observability/ERROR_LOG.jsonl` against the event schema (enum + required-field enforcement). |
| **Observability: Detect file collisions** | `detect_file_collisions.py` | Report active-writer collisions from the file-claim register. |
| **Observability: Snapshot git state** | `snapshot_git_state.py` | Capture branch/commit/dirty + staged/modified/untracked breakdown to `.chromatic/`. |
| **Observability: Summarize error patterns** | `summarize_error_patterns.py` | Aggregate recurring error signatures from the event log. |
| **Observability: Run all checks** | _(composite)_ | Runs the four tasks above in sequence. |

## Cross-platform notes

Each task invokes `python scripts/<name>.py` with **no shell-specific operators**
(no `&&`, pipes, or redirects), so the same `tasks.json` works on Windows
(PowerShell/cmd), macOS, and Linux. The scripts themselves are pure Python and
auto-detect the repo root, so tasks run correctly regardless of the active file
or working directory.

If you prefer a chained one-liner, use the composite **Run all checks** task
(which uses `dependsOrder: sequence`) rather than embedding shell `&&` — that
keeps the configuration portable.

## Customizing

- Add `--repo-root <path>` to a task's `command` to target a different checkout.
- `validate_event_schema.py` and `summarize_error_patterns.py` accept `--log`
  to point at an alternate JSONL event log.
