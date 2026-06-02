# Multi-Drive Rollout — chromatic-harness-v2

**Status:** Live as of 2026-06-02 on the originating workstation (`kas41`).
**Canonical SoT:** `E:\chromatic-harness-v2`

This guide documents an NTFS-junction topology for running `chromatic-harness-v2` across multiple drives on a single Windows workstation with one canonical clone serving as single source of truth.

## Topology

| Drive | Path | Mode | Notes |
|-------|------|------|-------|
| **E** | `E:\chromatic-harness-v2` | Canonical clone | Real git repo. All pulls and pushes happen here. |
| **C** | `C:\chromatic-harness-v2` | NTFS junction → E | Created via `mklink /J` or PowerShell `New-Item -ItemType Junction`. Zero bytes on disk, instant updates, no sync drift. |
| **D** | `D:\chromatic-harness-v2` | NTFS junction → E | Same as C. |
| *(cloud drives)* | *(none)* | Excluded | Google Drive, OneDrive, Dropbox-mounted volumes report a non-NTFS filesystem and Windows refuses cross-volume junctions. Even if forced, running a harness from a cloud-synced folder corrupts `.git` internals when the sync client touches loose objects. Projects on such drives must reference the canonical path explicitly. |

## Maintenance Protocol

1. **Pulls happen on the canonical clone only.** Never `git pull` from a junction path. The junction targets follow the canonical clone automatically.
2. **Pushes happen on the canonical clone only.** Same reason.
3. **Submodules** — `02_RUNTIME/runtime-engines/roach-pi` is a real git submodule. Use `git submodule update --remote` from the canonical clone only.
4. **bd CLI on Windows-native subprocess** — depends on a `bd.cmd` shim somewhere in Windows `PATH` that forwards to `bd-fallback.py`. Without it, `auto_intake.py` and similar callers fail with `[WinError 2] The system cannot find the file specified` because they invoke `subprocess.run(["bd", ...])` which can't see a Unix-style `bd` shim.
5. **`bd init` in this repo MUST use `--skip-agents`.** This repo owns its own `AGENTS.md`, `CLAUDE.md`, and `.claude/settings.json`. A vanilla `bd init` appends `## Beads Issue Tracker`, `## Session Completion`, and `## MANDATORY WORKFLOW` blocks to the wrappers, which pushes `CLAUDE.md` past the 50-line cap and duplicates content already in `AGENT_OPERATIONS.md`. The result fails 4 governance gates: `agent_operations`, `instruction_governance`, `instruction_drift`, `context_trim`. Correct invocation:
   ```bash
   bd init --skip-agents --non-interactive
   ```
   Only touches `.beads/` and git hooks; leaves wrappers untouched.
6. **Suspending a drive mirror** — `cmd /c "rmdir <X>:\chromatic-harness-v2"` removes the junction without affecting the canonical clone. Verify with `Get-Item <X>:\chromatic-harness-v2 -ErrorAction SilentlyContinue` returning null.
7. **Adding a new drive mirror** — `New-Item -ItemType Junction -Path '<X>:\chromatic-harness-v2' -Target '<canonical>'` from PowerShell. Local NTFS volumes only.

## Verification Commands

```powershell
# Byte-identity check across all mirrors (replace drive letters with your set)
'C','D','E' | ForEach-Object {
  Get-FileHash "${_}:\chromatic-harness-v2\CLAUDE.md" -Algorithm SHA256 | Select-Object Hash,Path
}

# Junction target inspection
fsutil reparsepoint query C:\chromatic-harness-v2
fsutil reparsepoint query D:\chromatic-harness-v2

# Validator from non-canonical cwd
Set-Location 'C:\Users\you'
python C:\chromatic-harness-v2\scripts\validate_claude_harness.py --root C:\chromatic-harness-v2
```

A passing setup yields identical SHA256 across all mirrors, `Reparse Tag Value : 0xa0000003` from `fsutil`, and `Claude harness validation OK` from the validator regardless of `cwd`.

## bd.cmd Shim Template

Drop the following at any location in Windows `PATH` (e.g. `%USERPROFILE%\.local\bin\bd.cmd`). UTF-8 without BOM, CRLF line endings:

```cmd
@echo off
REM bd shim for Windows-native subprocess calls
python "%USERPROFILE%\.claude\scripts\bd-fallback.py" %*
```

Confirms with `bd --version` from PowerShell returning `bd version <X> (Homebrew)` or similar.

## Rollback Procedure

```powershell
# 1. Restore archived global hooks (paths vary per machine)
Copy-Item '<backup>\settings.json.pre-harness-slim.bak' "$env:USERPROFILE\.claude\settings.json" -Force
Copy-Item '<backup>\CLAUDE.md.bak' "$env:USERPROFILE\.claude\CLAUDE.md" -Force

# 2. Remove junctions (does NOT delete canonical clone)
cmd /c "rmdir C:\chromatic-harness-v2"
cmd /c "rmdir D:\chromatic-harness-v2"

# 3. Optionally restore prior harness location

# 4. Restart Claude Code
```

## Known Yellow Findings (Not Topology-Related)

After a clean activation, the following are expected yellows from the standard daily audit — they do not indicate a broken rollout:

- **lock_metrics**: `lock_wait_p95_high` (~1500ms vs 1500ms threshold) on `intake_queue_mutation` lock. Self-recovers under normal load.
- **issues_awaiting_seeding (P3)**: Staged issues that need `python scripts/seed_issues_to_beads.py --apply`.

## Originating Rollout Notes (kas41 workstation, 2026-06-02)

- Old `E:\.00_Chromatic_Systems` (the prior `kas1987/ChromaticSystems` REPO-SYSTEMS python harness) was archived to `E:\.89_Gits\ChromaticSystems_legacy_20260602`. A second checkout of the same legacy repo on `feat/merge-chromatic-devsecops` remains at `E:\.89_Gits\ChromaticSystems` for branch work.
- Global `~/.claude/CLAUDE.md` references updated to point at the new canonical clone.
- Full rollback bundle staged at `~/.claude/_backups/rollout-v2-<timestamp>/`.
- `G:\` excluded because it is mounted as Google Drive (cloud-synced FAT32-presenting virtual volume).
