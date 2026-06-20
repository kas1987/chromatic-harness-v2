# switch_mcp_profile.ps1
# Switch the active MCP profile for Cursor/Claude in this harness project.
# Usage: powershell -File scripts\switch_mcp_profile.ps1 [local|remote]
#
# local  — stdio transport, runs mcp server in-process per IDE session (default, works anywhere)
# remote — sse transport, connects to desktop FastAPI server via HARNESS_API_URL env var

param(
    [ValidateSet("local", "remote")]
    [string]$Profile = "local"
)

$harness = Split-Path -Parent $PSScriptRoot
$profileSrc = Join-Path $harness "config\mcp-profiles\$Profile.json"
$cursorDst  = Join-Path $harness ".cursor\mcp.json"

if (-not (Test-Path $profileSrc)) {
    Write-Error "Profile not found: $profileSrc"
    exit 1
}

Copy-Item $profileSrc $cursorDst -Force
Write-Host "MCP profile set to: $Profile"
Write-Host "Written to: $cursorDst"

if ($Profile -eq "remote") {
    $host = $env:HARNESS_API_HOST
    $url  = $env:HARNESS_API_URL
    if (-not $host) {
        Write-Warning "HARNESS_API_HOST is not set. Set it to the desktop Tailscale IP (e.g. 100.x.x.x)."
    }
    if (-not $url) {
        Write-Warning "HARNESS_API_URL is not set. Set it to http://`$HARNESS_API_HOST:7700 (or your chosen port)."
    }
    Write-Host ""
    Write-Host "Required env vars for remote mode:"
    Write-Host "  HARNESS_API_HOST = <desktop Tailscale IP>"
    Write-Host "  HARNESS_API_URL  = http://<desktop Tailscale IP>:7700"
}

Write-Host ""
Write-Host "Restart Cursor/Claude Code to apply."
