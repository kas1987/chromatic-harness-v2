# setup_tailscale.ps1
# Companion script to setup_tailscale.bat -- runs as Administrator.
# Configures Tailscale to coexist with Surfshark by:
#   1. Stopping Surfshark WireGuard temporarily
#   2. Adding persistent bypass routes via LAN gateway (route -p)
#   3. Restarting Tailscale so it can reach control plane directly
#   4. Opening browser for Tailscale login, polling BackendState via JSON
#   5. Restarting Surfshark WireGuard

#Requires -RunAsAdministrator

$ErrorActionPreference = "Continue"

function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "> $msg" -ForegroundColor Cyan
}
function Write-OK([string]$msg)   { Write-Host "  OK: $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "  WARN: $msg" -ForegroundColor Yellow }

# -- Detect LAN gateway -------------------------------------------------------
Write-Step "Detecting LAN gateway..."

$lanRoute = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.NextHop -ne "0.0.0.0" -and
        $_.InterfaceAlias -notmatch "Surfshark|Tailscale|Loopback|WSL|vEthernet"
    } |
    Sort-Object RouteMetric |
    Select-Object -First 1

if (-not $lanRoute) {
    Write-Error "Could not detect LAN gateway. Ensure Wi-Fi or Ethernet is connected."
    exit 1
}

$GW      = $lanRoute.NextHop
$IfIndex = $lanRoute.ifIndex
$IfAlias = $lanRoute.InterfaceAlias
Write-OK "Gateway: $GW via $IfAlias (ifIndex $IfIndex)"

# -- Step 1: Stop Surfshark WireGuard -----------------------------------------
Write-Step "Stopping Surfshark WireGuard service..."
try {
    Stop-Service -Name "Surfshark WireGuard" -Force -ErrorAction Stop
    Write-OK "Surfshark WireGuard stopped"
} catch {
    Write-Warn "Could not stop Surfshark WireGuard: $_"
}
Start-Sleep -Seconds 2

# -- Step 2: Add persistent bypass routes via cmd route -p --------------------
# Tailscale ranges that must bypass Surfshark's tunnel.
# 'route -p' writes to HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\PersistentRoutes
Write-Step "Adding persistent bypass routes..."

$routes = @(
    @{ Net = "100.64.0.0";      Mask = "255.192.0.0";     Label = "100.64.0.0/10";      Desc = "Tailscale CGNAT mesh" },
    @{ Net = "100.100.100.100"; Mask = "255.255.255.255";  Label = "100.100.100.100/32"; Desc = "Tailscale MagicDNS" },
    @{ Net = "192.200.0.0";     Mask = "255.255.255.0";    Label = "192.200.0.0/24";     Desc = "controlplane.tailscale.com" }
)

foreach ($r in $routes) {
    $null = cmd /c "route delete $($r.Net)" 2>&1   # ignore "not found" errors
    $result = cmd /c "route -p add $($r.Net) MASK $($r.Mask) $GW METRIC 1" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-OK "$($r.Label) --> $GW  ($($r.Desc))"
    } else {
        Write-Warn "Failed to add route $($r.Label): $result"
    }
}

# -- Step 3: Restart Tailscale so it picks up the new routes ------------------
Write-Step "Restarting Tailscale service..."
Restart-Service -Name "Tailscale" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 4
Write-OK "Tailscale restarted"

# -- Step 4: Tailscale login --------------------------------------------------
Write-Step "Opening Tailscale login in your browser..."
Write-Host "  Sign in to your Tailscale account in the browser that opens." -ForegroundColor White
Write-Host "  This script will wait (up to 3 min) for you to complete login." -ForegroundColor White
Write-Host ""

Start-Process "tailscale" -ArgumentList "login" -NoNewWindow

# Poll BackendState via JSON -- the reliable way
$timeout  = 180
$elapsed  = 0
$interval = 5
$authed   = $false

while ($elapsed -lt $timeout) {
    Start-Sleep -Seconds $interval
    $elapsed += $interval

    try {
        $json = & tailscale status --json 2>$null | ConvertFrom-Json
        $state = $json.BackendState
        Write-Host "  State: $state ($elapsed/$timeout s)" -ForegroundColor DarkGray
        if ($state -eq "Running") {
            $authed = $true
            break
        }
    } catch {
        Write-Host "  Waiting... ($elapsed/$timeout s)" -ForegroundColor DarkGray
    }
}

if (-not $authed) {
    Write-Warn "Login not detected after $timeout s. Check the browser and re-run if needed."
    Write-Warn "Routes are already set -- next run will skip to 'tailscale up'."
} else {
    $ip = (& tailscale ip -4 2>$null)
    Write-OK "Authenticated! Your Tailscale IP: $ip"
}

# -- Step 5: tailscale up -----------------------------------------------------
Write-Step "Running tailscale up..."
& tailscale up --accept-routes 2>&1 | ForEach-Object { Write-Host "  $_" }

# -- Step 6: Restart Surfshark WireGuard --------------------------------------
Write-Step "Restarting Surfshark WireGuard..."
try {
    Start-Service -Name "Surfshark WireGuard" -ErrorAction Stop
    Start-Sleep -Seconds 3
    Write-OK "Surfshark WireGuard restarted"
} catch {
    Write-Warn "Could not auto-restart Surfshark WireGuard: $_"
    Write-Warn "Open the Surfshark app and reconnect manually."
}

# -- Final summary ------------------------------------------------------------
Write-Step "Done. Final state:"
Write-Host ""

Write-Host "Tailscale:" -ForegroundColor White
try {
    $json = & tailscale status --json 2>$null | ConvertFrom-Json
    Write-Host "  Backend : $($json.BackendState)"
    Write-Host "  Self IP : $(& tailscale ip -4 2>$null)"
} catch {
    & tailscale status 2>&1 | Select-Object -First 5 | ForEach-Object { Write-Host "  $_" }
}

Write-Host ""
Write-Host "Bypass routes:" -ForegroundColor White
foreach ($r in $routes) {
    $rt = cmd /c "route print $($r.Net)" 2>$null | Select-String $r.Net | Select-Object -First 1
    if ($rt) {
        Write-Host "  $($r.Label) -- active" -ForegroundColor Green
    } else {
        Write-Host "  $($r.Label) -- NOT FOUND" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "-----------------------------------------------------" -ForegroundColor DarkGray
Write-Host " Tailscale and Surfshark should now coexist."          -ForegroundColor White
Write-Host " Note your Tailscale IP above -- you will need it"     -ForegroundColor White
Write-Host " to configure the laptop in remote mode."              -ForegroundColor White
Write-Host "-----------------------------------------------------"  -ForegroundColor DarkGray
Write-Host ""
