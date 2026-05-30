# Idempotent Windows Task Scheduler install for Chromatic harness automation.
param(
    [string]$RepoRoot = "",
    [int]$IntakeMinutes = 15
)
$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
$RepoRoot = (Resolve-Path $RepoRoot).Path

$IntakeScript = Join-Path $RepoRoot "scripts\run_intake_cycle.ps1"
$SmokeScript = Join-Path $RepoRoot "scripts\smoke_stack.ps1"
$PreflightScript = Join-Path $RepoRoot "scripts\session_preflight.ps1"

foreach ($p in @($IntakeScript, $SmokeScript, $PreflightScript)) {
    if (-not (Test-Path $p)) { Write-Error "Missing script: $p" }
}

$runner = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File"

function Install-Task {
    param([string]$Name, [string]$ScriptPath, [string]$ExtraArgs)
    schtasks /Delete /TN $Name /F 2>$null | Out-Null
    $tr = "$runner `"$ScriptPath`""
    schtasks /Create /TN $Name /TR $tr /F $ExtraArgs | Out-Null
    Write-Host "Created: $Name"
}

Install-Task -Name "ChromaticIntakeCycle" -ScriptPath $IntakeScript `
    -ExtraArgs "/SC MINUTE /MO $IntakeMinutes"
Install-Task -Name "ChromaticSmokeDaily" -ScriptPath $SmokeScript `
    -ExtraArgs "/SC DAILY /ST 08:00"
Install-Task -Name "ChromaticSessionPreflight" -ScriptPath $PreflightScript `
    -ExtraArgs "/SC WEEKLY /D MON /ST 09:00"

Write-Host "Done. Query: schtasks /Query /TN ChromaticIntakeCycle"
Write-Host "Repo (scripts cd internally): $RepoRoot"
