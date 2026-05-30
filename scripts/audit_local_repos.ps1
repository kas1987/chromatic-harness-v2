#Requires -Version 5.1
<#
.SYNOPSIS
  Audit local git repos under the Chromatic workspace for harness v2 alignment.

.DESCRIPTION
  Scans C:\Users\kas41 (and optional extra roots) for directories containing .git,
  scores each against AGENT_OPERATIONS rig checks, and prints a markdown table.

.EXAMPLE
  powershell -File scripts/audit_local_repos.ps1
  powershell -File scripts/audit_local_repos.ps1 -Json
  powershell -File scripts/audit_local_repos.ps1 -Roots "D:\dev\other-rig"
#>
param(
    [string[]] $Roots = @($env:USERPROFILE),
    [string[]] $ProjectNames = @(
        'chromatic-harness-v2',
        'chromatic-stack',
        'chromatic-design-studios',
        'fusion-computer',
        'claude-powerline',
        '.claude',
        '.agents'
    ),
    [switch] $Json,
    [switch] $IncludeNested
)

$ErrorActionPreference = 'SilentlyContinue'

function Test-KnowledgeDirs {
    param([string]$AgentsPath)
    if (-not (Test-Path $AgentsPath)) { return $false }
    @('learnings', 'patterns', 'research') | Where-Object {
        Test-Path (Join-Path $AgentsPath $_)
    } | ForEach-Object { $_ }
}

function Get-RepoAudit {
    param([string]$Path)

    if (-not (Test-Path (Join-Path $Path '.git'))) { return $null }

    Push-Location $Path
    $remote = git remote get-url origin 2>$null
    $branch = git branch --show-current 2>$null
    $dirty = @(git status --short 2>$null).Count
    Pop-Location

    $agents = Join-Path $Path '.agents'
    $knowledge = Test-KnowledgeDirs $agents
    $hasKnowledge = ($knowledge -is [array] -and $knowledge.Count -gt 0) -or ($knowledge -is [string])

    $checks = @{
        agents_md     = Test-Path (Join-Path $Path 'AGENTS.md')
        claude_md     = Test-Path (Join-Path $Path 'CLAUDE.md')
        agents_dir    = Test-Path $agents
        knowledge     = $hasKnowledge
        handoff       = Test-Path (Join-Path $agents 'handoffs\latest.json')
        beads         = Test-Path (Join-Path $Path '.beads')
        remote        = [bool]$remote
    }

    $score = @($checks.Values | Where-Object { $_ }).Count
    $aligned = ($checks.agents_md -and $checks.claude_md -and $checks.agents_dir -and
                $checks.knowledge -and $checks.handoff -and $checks.beads -and $checks.remote)

    $status = if ($aligned) { 'Aligned' }
              elseif ($score -ge 4) { 'Partial' }
              elseif ($Path -eq $env:USERPROFILE) { 'P0 anti-pattern' }
              else { 'Legacy / out of band' }

    [PSCustomObject]@{
        Name       = Split-Path $Path -Leaf
        Path       = $Path
        Remote     = if ($remote) { $remote } else { '(none)' }
        Branch     = if ($branch) { $branch } else { '(detached?)' }
        DirtyFiles = $dirty
        Status     = $status
        Checks     = $checks
    }
}

function Find-ReposUnder {
    param([string]$Root, [int]$MaxDepth = 2)

    $found = @()
    if (Test-Path (Join-Path $Root '.git')) {
        return @($Root)
    }
    if ($MaxDepth -le 0) { return $found }

    Get-ChildItem -Path $Root -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $name = $_.Name
        if ($name -match '^(node_modules|\.git|venv|__pycache__|dist|build)$') { return }
        $found += Find-ReposUnder $_.FullName ($MaxDepth - 1)
    }
    return $found
}

$paths = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)

foreach ($root in $Roots) {
    if (-not $root) { continue }
    $expanded = [Environment]::ExpandEnvironmentVariables($root)
    if (-not (Test-Path $expanded)) { continue }

    foreach ($proj in $ProjectNames) {
        $p = Join-Path $expanded $proj
        if (Test-Path $p) { [void]$paths.Add($p) }
    }

    if ($IncludeNested) {
        foreach ($repo in (Find-ReposUnder $expanded 2)) {
            [void]$paths.Add($repo)
        }
    }
}

$audits = @()
foreach ($p in ($paths | Sort-Object)) {
    $a = Get-RepoAudit $p
    if ($null -ne $a) { $audits += $a }
}

if ($Json) {
    $payload = foreach ($item in $audits) {
        @{
            name   = $item.Name
            path   = $item.Path
            remote = $item.Remote
            branch = $item.Branch
            dirty  = $item.DirtyFiles
            status = $item.Status
            checks = $item.Checks
        }
    }
    $payload | ConvertTo-Json -Depth 5
    exit 0
}

function Format-YesNo($flag) {
    if ($flag) { return 'yes' }
    return '-'
}

$ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss') + ' UTC'
Write-Output ('# Local repo audit - ' + $ts)
Write-Output ''
$header = '| Name | Path | Remote | Branch | Dirty | Status |'
$sep = '|------|------|--------|--------|-------|--------|'
Write-Output $header
Write-Output $sep
foreach ($a in $audits) {
    $remoteShort = if ($a.Remote.Length -gt 48) { $a.Remote.Substring(0, 45) + '...' } else { $a.Remote }
    $row = '| {0} | {1} | {2} | {3} | {4} | {5} |' -f $a.Name, $a.Path, $remoteShort, $a.Branch, $a.DirtyFiles, $a.Status
    Write-Output $row
}
Write-Output ''
Write-Output '## Check matrix'
Write-Output ''
Write-Output '| Name | AGENTS | CLAUDE | .agents | knowledge | handoff | beads | remote |'
Write-Output '|------|--------|--------|---------|-----------|---------|-------|--------|'
foreach ($a in $audits) {
    $c = $a.Checks
    $row = '| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} |' -f `
        $a.Name, `
        (Format-YesNo $c.agents_md), `
        (Format-YesNo $c.claude_md), `
        (Format-YesNo $c.agents_dir), `
        (Format-YesNo $c.knowledge), `
        (Format-YesNo $c.handoff), `
        (Format-YesNo $c.beads), `
        (Format-YesNo $c.remote)
    Write-Output $row
}
Write-Output ""
Write-Output "See docs/REPO_AND_RIG_INVENTORY.md for full ecosystem map."
