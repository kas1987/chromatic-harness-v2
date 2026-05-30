# Scheduled / manual hands-off pre-session boot (no interactive bd).
param(
    [switch]$Force,
    [switch]$Full,
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$args = @("scripts/session_unified_guard.py", "--surface", "scheduler", "--invoked-by", "scheduler")
if ($Force) { $args += "--force" }
if ($Full) { $args += "--full" }
if ($DryRun) { $args += "--dry-run" }

python @args
exit $LASTEXITCODE
