# Sync lite Claude Code workflows from repo → ~/.claude/workflows/
# Backs up existing *.js to *.pre-sync.bak, skips *.HEAVY.js.bak

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Src = Join-Path $RepoRoot ".claude\workflows"
$Dest = Join-Path $env:USERPROFILE ".claude\workflows"

if (-not (Test-Path $Src)) {
    Write-Error "Missing $Src"
}

New-Item -ItemType Directory -Force -Path $Dest | Out-Null

Get-ChildItem $Src -Filter "*.js" | ForEach-Object {
    $target = Join-Path $Dest $_.Name
    if (Test-Path $target) {
        Copy-Item $target "$target.pre-sync.bak" -Force
        Write-Host "Backed up $($_.Name) -> $($_.Name).pre-sync.bak"
    }
    Copy-Item $_.FullName $target -Force
    Write-Host "Installed $($_.Name)"
}

Write-Host ""
Write-Host "Done. Heavy archived workflows (*.HEAVY.js.bak) are NOT installed."
Write-Host "Read docs/AGENT_ANTIPATTERNS.md before running /ship or /qa."
