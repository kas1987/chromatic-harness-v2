# Idempotent Windows Task Scheduler install for Chromatic harness automation.
param(
    [string]$RepoRoot = "",
    [int]$IntakeMinutes = 15
)
$ErrorActionPreference = "Continue"
if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
$RepoRoot = (Resolve-Path $RepoRoot).Path

$IntakeScript = Join-Path $RepoRoot "scripts\run_intake_cycle.ps1"
$SmokeScript = Join-Path $RepoRoot "scripts\smoke_stack.ps1"
$BootScript = Join-Path $RepoRoot "scripts\run_session_boot.ps1"
$PreflightScript = Join-Path $RepoRoot "scripts\session_preflight.ps1"
$CloseoutScript = Join-Path $RepoRoot "scripts\run_session_closeout.ps1"

foreach ($p in @($IntakeScript, $SmokeScript, $BootScript, $PreflightScript, $CloseoutScript)) {
    if (-not (Test-Path $p)) { Write-Error "Missing script: $p" }
}

function Install-Task {
    param(
        [string]$Name,
        [string]$ScriptPath,
        [string[]]$CreateArgs,
        [string]$ScriptArgs = ""
    )
    schtasks /Delete /TN $Name /F 2>$null | Out-Null
    $tr = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`" $ScriptArgs"
    $allArgs = @("/Create", "/TN", $Name, "/TR", $tr, "/F") + $CreateArgs
    $create = & schtasks @allArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Failed to create ${Name}: $create"
        return
    }
    Write-Host "Created: $Name"
}

Install-Task -Name "ChromaticIntakeCycle" -ScriptPath $IntakeScript `
    -CreateArgs @("/SC", "MINUTE", "/MO", "$IntakeMinutes")
Install-Task -Name "ChromaticSmokeDaily" -ScriptPath $SmokeScript `
    -CreateArgs @("/SC", "DAILY", "/ST", "08:00")
Install-Task -Name "ChromaticSessionBoot" -ScriptPath $BootScript `
    -CreateArgs @("/SC", "DAILY", "/ST", "07:55")
Install-Task -Name "ChromaticSessionPreflight" -ScriptPath $PreflightScript `
    -CreateArgs @("/SC", "WEEKLY", "/D", "MON", "/ST", "09:00") -ScriptArgs "-Full"
Install-Task -Name "ChromaticSessionCloseout" -ScriptPath $CloseoutScript `
    -CreateArgs @("/SC", "DAILY", "/ST", "22:00")

Write-Host "Done. Query: schtasks /Query /TN ChromaticSessionBoot"
Write-Host "Repo (scripts cd internally): $RepoRoot"
Write-Host "Cursor/Claude also run boot on sessionStart via hooks."
