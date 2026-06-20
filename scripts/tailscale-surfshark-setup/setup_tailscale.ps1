# setup_tailscale.ps1
# Companion script to setup_tailscale.bat — runs as Administrator.
# Configures Tailscale to coexist with Surfshark by:
#   - Temporarily stopping Surfshark WireGuard so Tailscale can authenticate
#   - Adding persistent bypass routes for Tailscale's IP ranges via the LAN gateway
#   - Restarting Surfshark WireGuard

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "► $msg" -ForegroundColor Cyan
}

function Write-OK([string]$msg) {
    Write-Host "  ✓ $msg" -ForegroundColor Green
}

function Write-Warn([string]$msg) {
    Write-Host "  ! $msg" -ForegroundColor Yellow
}

# ── Detect LAN gateway (not Surfshark, not Tailscale, not loopback) ──────────
Write-Step "Detecting LAN gateway..."

$lanRoute = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.NextHop -ne "0.0.0.0" -and
        $_.InterfaceAlias -notmatch "Surfshark|Tailscale|Loopback|WSL|vEthernet"
    } |
    Sort-Object RouteMetric |
    Select-Object -First 1

if (-not $lanRoute) {
    Write-Error "Could not detect LAN gateway. Make sure Wi-Fi or Ethernet is connected."
    exit 1
}

$GW      = $lanRoute.NextHop
$IfIndex = $lanRoute.ifIndex
$IfAlias = $lanRoute.InterfaceAlias
Write-OK "Gateway: $GW via $IfAlias (ifIndex $IfIndex)"

# ── Tailscale IP ranges to bypass Surfshark ───────────────────────────────────
# These routes send Tailscale's traffic directly through the LAN adapter,
# not through Surfshark's tunnel. Persistent (-PolicyStore PersistentStore)
# so they survive reboots.
$routes = @(
    @{ Prefix = "100.64.0.0/10";    Desc = "Tailscale CGNAT mesh range" },
    @{ Prefix = "100.100.100.100/32"; Desc = "Tailscale MagicDNS" },
    @{ Prefix = "192.200.0.0/24";   Desc = "controlplane.tailscale.com" }
)

# ── Step 1: Stop Surfshark WireGuard ─────────────────────────────────────────
Write-Step "Stopping Surfshark WireGuard service..."
try {
    Stop-Service -Name "Surfshark WireGuard" -Force -ErrorAction Stop
    Write-OK "Surfshark WireGuard stopped"
} catch {
    Write-Warn "Could not stop Surfshark WireGuard: $_"
    Write-Warn "Proceeding anyway — login may still succeed"
}

Start-Sleep -Seconds 2

# ── Step 2: Reset Tailscale to clear failed state ─────────────────────────────
Write-Step "Restarting Tailscale service..."
Restart-Service -Name "Tailscale" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Write-OK "Tailscale service restarted"

# ── Step 3: Tailscale login ───────────────────────────────────────────────────
Write-Step "Opening Tailscale login in your browser..."
Write-Host "  Complete the login in the browser window that opens." -ForegroundColor White
Write-Host "  This window will wait until authentication is confirmed." -ForegroundColor White

Start-Process "tailscale" -ArgumentList "login" -NoNewWindow

# Poll until authenticated (max 3 minutes)
$timeout  = 180
$elapsed  = 0
$interval = 5
$authed   = $false

while ($elapsed -lt $timeout) {
    Start-Sleep -Seconds $interval
    $elapsed += $interval
    $status = & tailscale status 2>&1
    if ($status -notmatch "NoState|NeedsLogin|Stopped|logged out") {
        $authed = $true
        break
    }
    Write-Host "  Waiting for login... ($elapsed/$timeout s)" -ForegroundColor DarkGray
}

if (-not $authed) {
    Write-Warn "Login timed out after $timeout seconds."
    Write-Warn "Re-run this script after completing the browser login."
} else {
    Write-OK "Tailscale authenticated!"
    $status | Select-Object -First 3 | ForEach-Object { Write-Host "  $_" }
}

# ── Step 4: Add persistent bypass routes ─────────────────────────────────────
Write-Step "Adding persistent bypass routes for Tailscale traffic..."

foreach ($r in $routes) {
    $parts    = $r.Prefix -split "/"
    $dest     = $parts[0]
    $prefix   = [int]$parts[1]
    try {
        # Remove existing conflicting route if present
        Remove-NetRoute -DestinationPrefix $r.Prefix -ErrorAction SilentlyContinue -Confirm:$false

        New-NetRoute `
            -DestinationPrefix $r.Prefix `
            -NextHop $GW `
            -InterfaceIndex $IfIndex `
            -RouteMetric 1 `
            -PolicyStore PersistentStore `
            -ErrorAction Stop | Out-Null

        Write-OK "$($r.Prefix) → $GW  ($($r.Desc))"
    } catch {
        Write-Warn "Route $($r.Prefix) skipped: $_"
    }
}

# ── Step 5: Bring Tailscale up ────────────────────────────────────────────────
Write-Step "Bringing Tailscale up..."
& tailscale up 2>&1 | ForEach-Object { Write-Host "  $_" }

# ── Step 6: Restart Surfshark WireGuard ──────────────────────────────────────
Write-Step "Restarting Surfshark WireGuard..."
try {
    Start-Service -Name "Surfshark WireGuard" -ErrorAction Stop
    Write-OK "Surfshark WireGuard restarted"
} catch {
    Write-Warn "Could not restart Surfshark WireGuard: $_"
    Write-Warn "Open Surfshark app and reconnect manually."
}

Start-Sleep -Seconds 3

# ── Final status ──────────────────────────────────────────────────────────────
Write-Step "Final status check..."
Write-Host ""
Write-Host "── Tailscale ─────────────────────────────────────" -ForegroundColor DarkGray
& tailscale status 2>&1 | Select-Object -First 10 | ForEach-Object { Write-Host "  $_" }

Write-Host ""
Write-Host "── Active bypass routes ──────────────────────────" -ForegroundColor DarkGray
foreach ($r in $routes) {
    $rt = Get-NetRoute -DestinationPrefix $r.Prefix -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($rt) {
        Write-Host "  $($r.Prefix) → $($rt.NextHop)  [$($rt.InterfaceAlias)]" -ForegroundColor Green
    } else {
        Write-Host "  $($r.Prefix) → NOT FOUND" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host " Setup complete. Both Tailscale and Surfshark"      -ForegroundColor White
Write-Host " should now run without conflict."                   -ForegroundColor White
Write-Host ""
Write-Host " To get your Tailscale IP (for laptop config):"     -ForegroundColor White
Write-Host "   tailscale ip -4"                                  -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host ""
