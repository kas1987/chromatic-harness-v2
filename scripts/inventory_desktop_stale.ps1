#Requires -Version 5.1
<#
.SYNOPSIS
  Inventory desktop git repos before a rebuild — flag any that are dirty,
  ahead of remote, local-only, or have unpushed branches.

.DESCRIPTION
  Scans one or more root directories for .git repos and classifies each as:
    Clean      — fully pushed, nothing local-only
    Dirty      — uncommitted changes
    Ahead      — commits not pushed to remote
    LocalOnly  — no remote configured
    LocalBranch — has branches that don't exist on remote
    Detached   — HEAD is detached

  Exits 0 when no P0 risk (LocalOnly / Ahead / Dirty) is found.
  Exits 1 when any P0-risk repo exists (safe-to-rebuild check fails).
  Exits 2 on script error.

  Writes output to 01_STATE/desktop_repo_inventory.json and prints markdown.

.PARAMETER Roots
  Root directories to scan (default: C:\Users\kas41 family of project roots).

.PARAMETER MaxDepth
  How deep to recurse for nested repos (default: 3).

.PARAMETER Json
  Emit JSON only (no markdown).

.PARAMETER OutFile
  Path to write JSON artifact (default: 01_STATE/desktop_repo_inventory.json).

.EXAMPLE
  # Run from laptop against local user profile (same paths as desktop)
  powershell -File scripts/inventory_desktop_stale.ps1

  # Run on the desktop itself
  powershell -File scripts/inventory_desktop_stale.ps1 -Roots "C:\Users\kas41"

  # JSON only for piping
  powershell -File scripts/inventory_desktop_stale.ps1 -Json
#>
param(
    [string[]] $Roots = @(
        'C:\Users\kas41',
        'C:\.01_Image Org',
        'C:\.04_Prism'
    ),
    [int]    $MaxDepth = 3,
    [switch] $Json,
    [string] $OutFile  = 'C:\Users\kas41\chromatic-harness-v2\01_STATE\desktop_repo_inventory.json'
)

$ErrorActionPreference = 'SilentlyContinue'
$script:exitCode = 0

# ---------- helpers ----------------------------------------------------------

function Find-GitRepos {
    param([string]$Root, [int]$Depth)
    if (-not (Test-Path $Root -PathType Container)) { return }
    if (Test-Path (Join-Path $Root '.git')) {
        [void]$script:repos.Add($Root)
        return
    }
    if ($Depth -le 0) { return }
    Get-ChildItem -Path $Root -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch '^(node_modules|\.git|venv|__pycache__|dist|build|\.next)$' } |
        ForEach-Object { Find-GitRepos $_.FullName ($Depth - 1) }
}

function Get-RepoState {
    param([string]$Path)

    Push-Location $Path
    $remote   = git remote get-url origin 2>$null
    $branch   = git branch --show-current 2>$null
    $head     = git rev-parse HEAD 2>$null

    # Detached HEAD
    if (-not $branch -and $head) {
        Pop-Location
        return [PSCustomObject]@{
            Path       = $Path
            Name       = Split-Path $Path -Leaf
            Remote     = '(none)'
            Branch     = '(detached)'
            Dirty      = 0
            AheadBy    = 0
            LocalBranches = @()
            Risk       = 'Detached'
            Notes      = 'HEAD is detached — snapshot state, verify before wipe'
        }
    }

    # Dirty
    $dirtyFiles = @(git status --short 2>$null | Where-Object { $_ }).Count

    # Ahead of remote
    $aheadBy = 0
    if ($remote -and $branch) {
        $aheadRaw = git rev-list --count "@{u}..HEAD" 2>$null
        if ($aheadRaw -match '^\d+$') { $aheadBy = [int]$aheadRaw }
    }

    # Local-only branches (no upstream)
    $localOnly = @(
        git branch --format='%(refname:short) %(upstream)' 2>$null |
            Where-Object { $_ -match '^(\S+)\s*$' } |
            ForEach-Object { ($_ -split '\s+')[0] }
    )

    Pop-Location

    # Classify risk
    $risk = 'Clean'
    $notes = @()

    if (-not $remote) {
        $risk = 'LocalOnly'
        $notes += 'No remote — work will be lost on rebuild'
        $script:exitCode = 1
    }
    if ($dirtyFiles -gt 0) {
        if ($risk -eq 'Clean') { $risk = 'Dirty' }
        $notes += "$dirtyFiles uncommitted file(s)"
        $script:exitCode = 1
    }
    if ($aheadBy -gt 0) {
        if ($risk -eq 'Clean') { $risk = 'Ahead' }
        $notes += "$aheadBy commit(s) not pushed"
        $script:exitCode = 1
    }
    if ($localOnly.Count -gt 0) {
        if ($risk -eq 'Clean') { $risk = 'LocalBranch' }
        $notes += "$($localOnly.Count) local-only branch(es): $($localOnly -join ', ')"
    }

    [PSCustomObject]@{
        Path          = $Path
        Name          = Split-Path $Path -Leaf
        Remote        = if ($remote) { $remote } else { '(none)' }
        Branch        = if ($branch) { $branch } else { '(none)' }
        Dirty         = $dirtyFiles
        AheadBy       = $aheadBy
        LocalBranches = $localOnly
        Risk          = $risk
        Notes         = if ($notes) { $notes -join '; ' } else { '' }
    }
}

# ---------- main -------------------------------------------------------------

$script:repos = [System.Collections.Generic.List[string]]::new()
foreach ($root in $Roots) {
    $expanded = [Environment]::ExpandEnvironmentVariables($root)
    Find-GitRepos $expanded $MaxDepth
}

$results = foreach ($repo in ($script:repos | Sort-Object)) {
    Get-RepoState $repo
}

$ts = (Get-Date).ToUniversalTime().ToString('o')
$summary = @{
    generated_at = $ts
    scanned_roots = $Roots
    total_repos  = @($results).Count
    clean        = @($results | Where-Object Risk -eq 'Clean').Count
    dirty        = @($results | Where-Object Risk -eq 'Dirty').Count
    ahead        = @($results | Where-Object Risk -eq 'Ahead').Count
    local_only   = @($results | Where-Object Risk -eq 'LocalOnly').Count
    local_branch = @($results | Where-Object Risk -eq 'LocalBranch').Count
    detached     = @($results | Where-Object Risk -eq 'Detached').Count
    p0_risk      = ($script:exitCode -eq 1)
    repos        = @($results | ForEach-Object {
        @{
            name          = $_.Name
            path          = $_.Path
            remote        = $_.Remote
            branch        = $_.Branch
            dirty         = $_.Dirty
            ahead_by      = $_.AheadBy
            local_branches = $_.LocalBranches
            risk          = $_.Risk
            notes         = $_.Notes
        }
    })
}

# Write JSON artifact
try {
    $dir = Split-Path $OutFile
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
    $summary | ConvertTo-Json -Depth 6 | Set-Content -Path $OutFile -Encoding UTF8
} catch { Write-Warning "Could not write artifact to $OutFile : $_" }

if ($Json) {
    $summary | ConvertTo-Json -Depth 6
    exit $script:exitCode
}

# ---------- markdown output --------------------------------------------------

Write-Output ''
Write-Output ('# Desktop repo inventory — ' + (Get-Date -Format 'yyyy-MM-dd HH:mm') + ' UTC')
Write-Output ''
Write-Output ('Scanned: ' + ($Roots -join ', '))
Write-Output ('Total repos: ' + $summary.total_repos + '  |  Clean: ' + $summary.clean + '  |  Dirty: ' + $summary.dirty + '  |  Ahead: ' + $summary.ahead + '  |  LocalOnly: ' + $summary.local_only)
Write-Output ''

Write-Output '| # | Name | Branch | Dirty | Ahead | Risk | Notes |'
Write-Output '|---|------|--------|-------|-------|------|-------|'
$i = 1
foreach ($r in ($results | Sort-Object Risk, Name)) {
    $riskIcon = switch ($r.Risk) {
        'Clean'       { '✓' }
        'LocalOnly'   { '🔴' }
        'Dirty'       { '🟡' }
        'Ahead'       { '🟡' }
        'LocalBranch' { '🟠' }
        'Detached'    { '🟠' }
        default       { '?' }
    }
    $row = '| {0} | {1} | {2} | {3} | {4} | {5} {6} | {7} |' -f `
        $i, $r.Name, $r.Branch, $r.Dirty, $r.AheadBy, $riskIcon, $r.Risk, $r.Notes
    Write-Output $row
    $i++
}

Write-Output ''
if ($script:exitCode -eq 1) {
    Write-Output '## ⚠ P0 RISK: Desktop has unpushed/local work — DO NOT rebuild until resolved.'
} else {
    Write-Output '## ✓ Safe to rebuild — no local-only work detected.'
}
Write-Output ''
Write-Output "Artifact: $OutFile"

exit $script:exitCode
