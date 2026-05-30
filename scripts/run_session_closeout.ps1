# Harness session closeout (Task Scheduler / manual)
param(
    [string]$RepoRoot = "",
    [switch]$SpawnSuccessor
)
$ErrorActionPreference = "Continue"
if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
$RepoRoot = (Resolve-Path $RepoRoot).Path
Set-Location $RepoRoot
$args = @("scripts/session_closeout.py", "--invoked-by", "scheduler")
if ($SpawnSuccessor) { $args += "--spawn-successor" }
python @args
exit $LASTEXITCODE
