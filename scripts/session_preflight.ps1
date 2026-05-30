# Full pre-session: automated boot + bd ready (for manual/CI/deep checks).
param(
    [switch]$StrictMcp,
    [switch]$Force,
    [switch]$Full
)
$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$failed = 0

function Run-Step {
    param([string]$Name, [string[]]$Args)
    Write-Host "`n=== $Name ==="
    & python @Args
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "$Name exited $LASTEXITCODE"
        $script:failed = 1
    }
}

$bootArgs = @("scripts/session_boot_automation.py", "--invoked-by", "preflight")
if ($Force) { $bootArgs += "--force" }
if ($Full) { $bootArgs += "--full" }
Run-Step "session_boot_automation" $bootArgs

if ($StrictMcp) {
    Run-Step "audit_mcp_strict" @(
        "scripts/audit_mcp_context.py", "--profile", "harness_dev", "--strict"
    )
}

Write-Host "`n=== bd ready ==="
try {
    bd ready
    if ($LASTEXITCODE -ne 0) { $failed = 1 }
} catch {
    Write-Warning "bd not available: $_"
}

$manifest = Join-Path $RepoRoot "07_LOGS_AND_AUDIT\pre_session\latest.json"
if (Test-Path $manifest) {
    Write-Host "`nManifest: $manifest"
} else {
    Write-Warning "Manifest not written: $manifest"
    $failed = 1
}

if ($failed -ne 0) { exit 1 }
Write-Host "`nPreflight complete."
exit 0
