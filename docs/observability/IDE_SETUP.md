# IDE Setup: Chromatic Harness Observability

Use the included `.vscode/tasks.json` commands:

- `Harness: Validate Observability Logs`
- `Harness: Detect File Collisions`
- `Harness: Snapshot Git State`
- `Harness: Generate Observability Report`

Before editing files, an agent should run:

```bash
python scripts/claim_files.py --writer codex --session SESSION_ID --task TASK_ID --files path/to/file
```

After completing or aborting work:

```bash
python scripts/release_files.py --session SESSION_ID --all-for-session
```

Prefer wrapping risky commands:

```bash
python scripts/harness_run.py --route -- npm run build
```
