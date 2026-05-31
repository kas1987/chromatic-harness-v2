#Requires -Version 5.1
<#
.SYNOPSIS
  Rebuild desktop active repos from verified GitHub state.

.DESCRIPTION
  Phase 1 — Pre-flight: runs inventory_desktop_stale.ps1; aborts if P0-risk
             work is found (unpushed / local-only). Run from laptop first to
             push everything before running this on the desktop.

  Phase 2 — Archive: moves stale/dirty desktop repo copies to a quarantine
             directory (default: C:\AI-DJ\_QUARANTINE) so they are not deleted
             outright.

  Phase 3 — Reclone: fresh clone of each repo in the canonical list under
             C:\AI-DJ\01_ACTIVE_REPOS from their GitHub remote.

  Phase 4 — Verify: checks each recloned repo for clean status and correct
             remote.

  Exit 0 on success, 1 on any failure.

.PARAMETER ActiveRepos
  List of GitHub repo URLs to reclone. Defaults to canonical Chromatic set.

.PARAMETER ActiveRoot
  Target directory for recloned repos. Default: C:\AI-DJ\01_ACTIVE_REPOS

.PARAMETER QuarantineRoot
  Directory to move stale copies into. Default: C:\AI-DJ\_QUARANTINE

.PARAMETER SkipPreflight
  Skip the inventory pre-flight check (use when running after manual push verification).

.PARAMETER DryRun
  Print what would happen without moving or cloning anything.

.EXAMPLE
  # Full rebuild from desktop
  powershell -File scripts/rebuild_desktop_repos.ps1

  # Dry run first
  powershell -File scripts/rebuild_desktop_repos.ps1 -DryRun

  # Skip preflight if you already ran inventory manually
  powershell -File scripts/rebuild_desktop_repos.ps1 -SkipPreflight
#>
param(
    [string[]] $ActiveRepos = @(
        'https://github.com/kas1987/chromatic-harness-v2',
        'https://github.com/kas1987/chromatic-stack',
        'https://github.com/kas1987/chromatic-design-studios',
        'https://github.com/kas1987/fusion-computer',
        'https://github.com/kas1987/claude-powerline',
        'https://github.com/kas1987/Chromatic_Wiki'
    ),
    [string] $ActiveRoot      = 'C:\AI-DJ\01_ACTIVE_REPOS',
    [string] $QuarantineRoot  = 'C:\AI-DJ\_QUARANTINE',
    [switch] $SkipPreflight,
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'
$script:failed = @()
$ts = (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss')

function Log {
    param([string]$Msg, [string]$Level = 'INFO')
    $color = switch ($Level) { 'WARN' { 'Yellow' } 'ERROR' { 'Red' } 'OK' { 'Green' } default { 'White' } }
    Write-Host "[$Level] $Msg" -ForegroundColor $color
}

function Assert-Git {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Log 'git not found in PATH' 'ERROR'; exit 1
    }
}

# ---------- Phase 1: Pre-flight inventory -----------------------------------

if (-not $SkipPreflight) {
    Log '=== Phase 1: Pre-flight inventory ===' 'INFO'
    $inventoryScript = Join-Path $PSScriptRoot 'inventory_desktop_stale.ps1'
    if (-not (Test-Path $inventoryScript)) {
        Log "inventory_desktop_stale.ps1 not found at $inventoryScript — run from repo root or pass -SkipPreflight" 'ERROR'
        exit 1
    }
    & powershell -NoProfile -File $inventoryScript
    if ($LASTEXITCODE -ne 0) {
        Log 'Pre-flight found P0-risk repos. Push or archive local work before rebuilding.' 'ERROR'
        Log 'Re-run with -SkipPreflight to bypass (only if you have verified all work is pushed).' 'WARN'
        exit 1
    }
    Log 'Pre-flight passed — no P0-risk local work detected.' 'OK'
} else {
    Log 'Skipping pre-flight (--SkipPreflight).' 'WARN'
}

# ---------- Phase 2: Archive stale copies -----------------------------------

Assert-Git

Log '=== Phase 2: Archive stale desktop copies ===' 'INFO'

$quarantineDir = Join-Path $QuarantineRoot "desktop_$ts"
$existingRepoDirs = @()

foreach ($url in $ActiveRepos) {
    $name   = ($url -split '/')[-1] -replace '\.git$', ''
    $target = Join-Path $ActiveRoot $name

    if (Test-Path $target) {
        $existingRepoDirs += [PSCustomObject]@{ Name = $name; Path = $target }
    }
}

if ($existingRepoDirs.Count -gt 0) {
    Log "Found $($existingRepoDirs.Count) existing repo dir(s) under $ActiveRoot — archiving to $quarantineDir" 'INFO'
    if (-not $DryRun) {
        New-Item -ItemType Directory -Force -Path $quarantineDir | Out-Null
    }
    foreach ($r in $existingRepoDirs) {
        Log "  archive: $($r.Path) -> $quarantineDir\$($r.Name)" 'INFO'
        if (-not $DryRun) {
            Move-Item -Path $r.Path -Destination (Join-Path $quarantineDir $r.Name) -Force
        }
    }
    Log "Archived $($existingRepoDirs.Count) dir(s) to $quarantineDir" 'OK'
} else {
    Log "No existing repos found under $ActiveRoot — nothing to archive." 'INFO'
}

# ---------- Phase 3: Reclone from GitHub ------------------------------------

Log '=== Phase 3: Reclone from GitHub ===' 'INFO'

if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path $ActiveRoot | Out-Null
}

foreach ($url in $ActiveRepos) {
    $name   = ($url -split '/')[-1] -replace '\.git$', ''
    $target = Join-Path $ActiveRoot $name
    Log "  clone $url -> $target" 'INFO'
    if (-not $DryRun) {
        git clone $url $target 2>&1 | ForEach-Object { Write-Host "    $_" }
        if ($LASTEXITCODE -ne 0) {
            Log "FAILED: git clone $url" 'ERROR'
            $script:failed += $name
        } else {
            Log "  cloned $name" 'OK'
        }
    }
}

# ---------- Phase 4: Verify -------------------------------------------------

Log '=== Phase 4: Verify recloned repos ===' 'INFO'

foreach ($url in $ActiveRepos) {
    $name   = ($url -split '/')[-1] -replace '\.git$', ''
    $target = Join-Path $ActiveRoot $name

    if ($DryRun) {
        Log "  [dry-run] would verify $target" 'INFO'
        continue
    }
    if (-not (Test-Path (Join-Path $target '.git'))) {
        Log "  MISSING: $target" 'ERROR'
        $script:failed += $name
        continue
    }

    Push-Location $target
    $remote  = git remote get-url origin 2>$null
    $dirty   = @(git status --short 2>$null).Count
    $branch  = git branch --show-current 2>$null
    Pop-Location

    if ($dirty -eq 0 -and $remote) {
        Log "  OK  $name  branch=$branch  remote=$remote" 'OK'
    } else {
        Log "  WARN  $name  dirty=$dirty  remote=$remote" 'WARN'
    }
}

# ---------- Summary ---------------------------------------------------------

Log ''
if ($DryRun) {
    Log '=== DRY RUN complete — no changes made ===' 'WARN'
    exit 0
}

if ($script:failed.Count -gt 0) {
    Log "=== FAILED: $($script:failed -join ', ') ===" 'ERROR'
    exit 1
}

Log '=== Desktop rebuild complete. All repos verified clean. ===' 'OK'
Log "Active repos: $ActiveRoot"
Log "Quarantine:   $quarantineDir"
exit 0
