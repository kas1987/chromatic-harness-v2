# Large-File & Log Hygiene Policy

How this repo keeps generated logs and large blobs out of git history (so pushes
don't trip GitHub's 50 MB LFS warning and the repo stays clone-friendly).

## The three controls

1. **`.gitignore` for generated output.** Every rolling log / telemetry file is
   ignored (`07_LOGS_AND_AUDIT/**/*.jsonl` per-run dumps, `docs/workflows/WORKFLOW_RUN_LOG.jsonl`,
   runtime `logs/*.jsonl`, sqlite caches, etc.). Adding a *new* writer? Add its
   output path to `.gitignore` in the same change.

2. **`scripts/large_file_gate.py` (blocking gate).** Runs in:
   - `git_hooks/pre-commit` (`--staged`) — blocks the commit.
   - `.github/workflows/ci.yml` governance gate (`--all`) — blocks the PR.

   It fails on:
   - any file ≥ **45 MB** (just under GitHub's hard warning); warns at ≥ 5 MB.
   - any staged/tracked file that **matches `.gitignore`** (catches a generated
     log being force-added back, which is how `WORKFLOW_RUN_LOG.jsonl` became a
     59 MB tracked blob).

   Genuine large assets that must live in git go through **Git LFS** and are
   listed in `.large-file-allowlist` (one fnmatch glob per line).

3. **`scripts/log_retention.py` (rotation + pruning).**
   - `prune_dir` — deletes old dated per-run files, keeping newest N. Protected
     files (`latest.json`, `*_latest.json`, `history.jsonl`, `*.md`, schemas) are
     never pruned.
   - `rotate_jsonl` — caps *protected, tracked* append-only logs (`history.jsonl`)
     by line **or byte** count, archiving the dropped prefix. `token_governance`
     entries are large, so that target is byte-capped (4 MB). Wired into the
     `token_governance_closed_loop.py` writer and runnable on demand:

     ```bash
     python scripts/log_retention.py --rotate --apply --archive ~/harness_cleanup_archive
     python scripts/log_retention.py --all --apply        # prune per-run exhaust
     ```

## If a push warns about a large file

1. Confirm it should not be in git → add to `.gitignore`, then
   `git rm --cached <file>` (keeps it on disk) and commit.
2. If it is a genuine asset → `git lfs track` it and add a glob to
   `.large-file-allowlist`.
3. To purge a large blob already in *history* (rewrites history, force-push):
   that is a **T4** operation — get explicit approval first.
