# Beads Dolt sync troubleshooting

Cross-machine beads sync uses `bd dolt push` / `bd dolt pull` against `refs/dolt/data` on your git remote — not `.beads/issues.jsonl` (export only). See [SYNC_CONCEPTS](https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md).

## Quick checks

```bash
bd dolt status
bd dolt remote list
python scripts/check_beads_dolt_health.py --try-push
```

## Common failures

### `ambiguous argument 'HEAD'`

**Cause:** Dolt's `git-remote-cache` bare repo has `refs/heads/master` with zero commits.

**Fix (automated):**

```bash
python scripts/check_beads_dolt_health.py
```

**Fix (manual):**

```powershell
$gitDir = ".beads\embeddeddolt\chromatic_harness_v2\.dolt\git-remote-cache\*\repo.git"
$emptyTree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
$commit = git --git-dir=$gitDir commit-tree $emptyTree -m "dolt remote cache bootstrap"
git --git-dir=$gitDir update-ref refs/heads/master $commit
```

### `direct push to main/master is blocked`

**Cause:** Global/repo `pre-push` hooks block `master`/`main`; Dolt cache repos use `master`.

**Fix:** Pre-push hooks must allow `refs/dolt/*` (see `.beads/hooks/pre-push.sh`). Sync to `~/.claude/hooks/pre-push.sh` if you use git templates.

### `couldn't find remote ref refs/dolt/data`

**Expected on first push** — the ref is created on first successful `bd dolt push`.

### HTTPS / credential hints

Configure non-interactive auth (Git Credential Manager, `GITHUB_TOKEN`, or SSH remote). Dolt does not support interactive prompts.

```bash
bd dolt remote add origin https://github.com/<org>/<repo>.git
```

### No Dolt remote configured

```bash
bd dolt remote add origin "$(bd config get sync.remote 2>/dev/null || echo <your-repo-url>)"
bd dolt push
```

## Session closeout

1. `bd dolt commit` (if using batch auto-commit)
2. `bd dolt push`
3. `git push` (code branch)

Health script (warning in CI, strict optional):

```bash
python scripts/check_beads_dolt_health.py --try-push --strict
```
