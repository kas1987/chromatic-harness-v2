# Pre-session checks: context report, MCP audit, intake validation, bd ready.
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

Run-Step "session_context_report" @(
    "scripts/session_context_report.py", "--log", "--invoked-by", "cursor"
)
Run-Step "audit_mcp_context" @(
    "scripts/audit_mcp_context.py", "--profile", "harness_dev"
)
Run-Step "validate_intake_loop" @("scripts/validate_intake_loop.py")

Write-Host "`n=== bd ready ==="
try {
    bd ready
    if ($LASTEXITCODE -ne 0) { $failed = 1 }
} catch {
    Write-Warning "bd not available: $_"
}

if ($failed -ne 0) { exit 1 }
Write-Host "`nPreflight complete."
exit 0
