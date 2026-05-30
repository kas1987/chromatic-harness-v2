# Bounded docker compose smoke: API health + optional console (timeouts avoid hung curl).
param(
    [int]$ApiTimeoutSec = 10,
    [int]$ConsoleTimeoutSec = 15,
    [switch]$SkipConsole
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$DeployDir = Join-Path $RepoRoot "09_DEPLOYMENT"
Set-Location $DeployDir

Write-Host "=== docker compose ps ==="
docker compose ps
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

function Invoke-CurlStatus {
    param([string]$Url, [int]$TimeoutSec)
    try {
        $resp = curl.exe -s -o NUL -w "%{http_code}" --max-time $TimeoutSec $Url 2>&1
        return [int]$resp
    } catch {
        return 0
    }
}

$apiCode = Invoke-CurlStatus -Url "http://127.0.0.1:8787/health" -TimeoutSec $ApiTimeoutSec
Write-Host "API /health HTTP $apiCode (timeout ${ApiTimeoutSec}s)"
if ($apiCode -lt 200 -or $apiCode -ge 400) {
    Write-Error "API health check failed"
}

if (-not $SkipConsole) {
    $consoleCode = Invoke-CurlStatus -Url "http://127.0.0.1:3030/" -TimeoutSec $ConsoleTimeoutSec
    Write-Host "Console / HTTP $consoleCode (timeout ${ConsoleTimeoutSec}s)"
    if ($consoleCode -lt 200 -or $consoleCode -ge 500) {
        Write-Warning "Console check failed or still starting (dev/prod build may need warm-up)"
    }
}

Write-Host "Smoke stack OK (API)"
exit 0
