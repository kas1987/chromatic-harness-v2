# start_harness_api.ps1
# Start the Chromatic Harness FastAPI server (02_RUNTIME/api/main.py).
# Intended to run on the DESKTOP as a persistent service reachable via Tailscale.
#
# Usage: powershell -File scripts\start_harness_api.ps1 [-Port 7700] [-Host 0.0.0.0]

param(
    [int]$Port = 7700,
    [string]$BindHost = "0.0.0.0"
)

$harness = Split-Path -Parent $PSScriptRoot
$apiDir  = Join-Path $harness "02_RUNTIME\api"

if (-not (Test-Path $apiDir)) {
    Write-Error "API directory not found: $apiDir"
    exit 1
}

# Verify uvicorn is available
$uvicorn = Get-Command uvicorn -ErrorAction SilentlyContinue
if (-not $uvicorn) {
    Write-Error "uvicorn not found. Run: pip install uvicorn fastapi aiosqlite"
    exit 1
}

Write-Host "Starting Chromatic Harness API..."
Write-Host "  Listening on http://$BindHost`:$Port"
Write-Host "  API docs:    http://localhost:$Port/docs"
Write-Host "  Health:      http://localhost:$Port/health"
Write-Host ""
Write-Host "To reach this from the laptop via Tailscale:"
Write-Host "  Set HARNESS_API_HOST=<this machine Tailscale IP>"
Write-Host "  Set HARNESS_API_URL=http://<this machine Tailscale IP>:$Port"
Write-Host ""

Set-Location $apiDir
$env:PYTHONPATH = "$harness\02_RUNTIME;$apiDir"
uvicorn main:app --host $BindHost --port $Port --reload
