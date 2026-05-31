# Repo Sync Health

> Source of truth for local ↔ GitHub repo sync state across laptop and desktop.
> Regenerate: `powershell -File scripts/inventory_desktop_stale.ps1`
> Rebuild desktop: `powershell -File scripts/rebuild_desktop_repos.ps1 -DryRun`

## Canonical Paths

| Machine  | Root                            |
|----------|---------------------------------|
| Laptop   | `C:\Users\kas41`                |
| Desktop  | `C:\AI-DJ\01_ACTIVE_REPOS`      |
| Quarantine | `C:\AI-DJ\_QUARANTINE`        |

## Canonical Repo Set (GitHub source of truth)

| Repo | Remote | Notes |
|------|--------|-------|
| chromatic-harness-v2 | github.com/kas1987/chromatic-harness-v2 | Primary harness |
| chromatic-stack | github.com/kas1987/chromatic-stack | Stack runtime |
| chromatic-design-studios | github.com/kas1987/chromatic-design-studios | Design layer |
| fusion-computer | github.com/kas1987/fusion-computer | Fusion compute |
| claude-powerline | github.com/kas1987/claude-powerline | Statusline |
| Chromatic_Wiki | github.com/kas1987/Chromatic_Wiki | Wiki / learnings |
| .claude | github.com/kas1987/.claude | Global Claude config |

## Laptop Status (last scan: 2026-05-31)

See `01_STATE/desktop_repo_inventory.json` for full machine-readable state.
Run `powershell -File scripts/inventory_desktop_stale.ps1` to refresh.

| Repo | Risk | Notes |
|------|------|-------|
| chromatic-harness-v2 | Clean | Primary working repo |
| Chromatic_Wiki | Clean | |
| chromatic-design-studios | Clean | |
| fusion-computer | Clean | |
| skills | Clean | |
| .claude | Dirty | 5 uncommitted files; many local swarm branches |
| .oh-my-bash | Dirty | 1 uncommitted file |
| .04_Prism | LocalBranch | `main` branch local-only |
| chromatic-stack | LocalBranch | `master` branch local-only |
| claude-powerline | LocalBranch | `kas41/context-thresholds` local-only |
| .01_Image Org | LocalBranch | 2 worktree-agent branches local-only |
| chromatic-wiki | LocalBranch | auto-promote branch local-only |
| plugin | Ahead | 2 commits not pushed |
| zelexdoll-theme | LocalOnly | **No remote** — not in canonical set; intentionally excluded from rebuild |
| .pyenv | Detached | Snapshot — not a source repo |

## Desktop Status

Desktop has not been rebuilt yet. Run `rebuild_desktop_repos.ps1` to establish
`C:\AI-DJ\01_ACTIVE_REPOS` as the clean desktop working root.

## Drift Protocol

1. Run `inventory_desktop_stale.ps1` weekly (or before any desktop work)
2. Any `Ahead` or `LocalOnly` repos → push or create remote before switching machines
3. After desktop rebuild, re-run inventory to confirm clean state
4. Update this file and `repo-sync-registry.json` after each audit

## Related Files

- `01_STATE/repo-sync-registry.csv` — machine-readable registry (all 17 repos)
- `01_STATE/repo-sync-registry.json` — JSON version with paths
- `01_STATE/desktop_repo_inventory.json` — last inventory run output
- `scripts/inventory_desktop_stale.ps1` — inventory script
- `scripts/rebuild_desktop_repos.ps1` — desktop rebuild script
