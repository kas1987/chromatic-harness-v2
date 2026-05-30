# Poll inbox -> auto_intake with JSONL audit log (Windows Task Scheduler friendly).
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

# Concurrent-run guard: exit immediately if another instance is already running.
# Prevents multiple Task Scheduler firings from contending on intake_queue_mutation lock.
$LockFile = Join-Path $env:TEMP "chromatic_intake_cycle.lock"
$MyPid = $PID
if (Test-Path $LockFile) {
    $OtherPid = Get-Content $LockFile -ErrorAction SilentlyContinue
    if ($OtherPid -and (Get-Process -Id ([int]$OtherPid) -ErrorAction SilentlyContinue)) {
        Write-Host "run_intake_cycle: already running (pid=$OtherPid), skipping"
        exit 0
    }
}
Set-Content $LockFile $MyPid -Encoding utf8
try {

$LogDir = Join-Path $RepoRoot "07_LOGS_AND_AUDIT\intake_cycle"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}
$LogFile = Join-Path $LogDir ("cycle_{0:yyyyMMdd}.jsonl" -f (Get-Date))

$Limit = 10
if ($env:CHROMATIC_INTAKE_LIMIT) {
    $Limit = [int]$env:CHROMATIC_INTAKE_LIMIT
}

$started = (Get-Date).ToUniversalTime().ToString("o")
$pollExit = 0
$intakeExit = 0
$pollOut = ""
$intakeOut = ""

try {
    $pollProc = Start-Process -FilePath "python" -ArgumentList @(
        "scripts/poll_inbox.py", "--limit", "$Limit"
    ) -WorkingDirectory $RepoRoot -Wait -PassThru -NoNewWindow `
        -RedirectStandardOutput "$env:TEMP\chromatic_poll_out.txt" `
        -RedirectStandardError "$env:TEMP\chromatic_poll_err.txt"
    $pollExit = $pollProc.ExitCode
    $pollOut = Get-Content "$env:TEMP\chromatic_poll_out.txt" -Raw -ErrorAction SilentlyContinue
} catch {
    $pollExit = 1
    $pollOut = $_.Exception.Message
}

try {
    $intakeProc = Start-Process -FilePath "python" -ArgumentList @(
        "scripts/auto_intake.py", "--limit", "$Limit"
    ) -WorkingDirectory $RepoRoot -Wait -PassThru -NoNewWindow `
        -RedirectStandardOutput "$env:TEMP\chromatic_intake_out.txt" `
        -RedirectStandardError "$env:TEMP\chromatic_intake_err.txt"
    $intakeExit = $intakeProc.ExitCode
    $intakeOut = Get-Content "$env:TEMP\chromatic_intake_out.txt" -Raw -ErrorAction SilentlyContinue
} catch {
    $intakeExit = 1
    $intakeOut = $_.Exception.Message
}

$record = @{
    started_at = $started
    finished_at = (Get-Date).ToUniversalTime().ToString("o")
    poll_exit = $pollExit
    intake_exit = $intakeExit
    limit = $Limit
    poll_report = $null
    intake_report = $null
}
try {
    if ($pollOut -and $pollOut.Trim()) { $record.poll_report = $pollOut | ConvertFrom-Json }
} catch { $record.poll_report_raw = $pollOut }
try {
    if ($intakeOut -and $intakeOut.Trim()) { $record.intake_report = $intakeOut | ConvertFrom-Json }
} catch { $record.intake_report_raw = $intakeOut }

$line = $record | ConvertTo-Json -Compress -Depth 8
Add-Content -Path $LogFile -Value $line -Encoding utf8
Write-Host $line

if ($pollExit -ne 0 -or $intakeExit -ne 0) { exit 1 }
exit 0
} finally {
    # Release concurrent-run guard lock file
    Remove-Item $LockFile -ErrorAction SilentlyContinue
}
