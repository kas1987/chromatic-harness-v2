# Scheduled / manual hands-off pre-session boot (no interactive bd).
param(
    [switch]$Force,
    [switch]$Full
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$args = @("scripts/session_boot_automation.py", "--invoked-by", "scheduler")
if ($Force) { $args += "--force" }
if ($Full) { $args += "--full" }

python @args
exit $LASTEXITCODE
