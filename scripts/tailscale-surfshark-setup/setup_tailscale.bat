@echo off
:: setup_tailscale.bat
:: Configures Tailscale to coexist with Surfshark VPN.
:: Run this once. Does NOT require closing Surfshark.
::
:: What it does:
::   1. Elevates to Administrator
::   2. Stops Surfshark WireGuard temporarily
::   3. Logs into Tailscale (opens browser)
::   4. Adds persistent bypass routes so Tailscale traffic skips Surfshark
::   5. Restarts Surfshark WireGuard
::
:: After this runs, both VPNs coexist without conflict.

setlocal

:: ── Elevation check ────────────────────────────────────────────────────────
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Requesting Administrator rights...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

:: ── Run the PowerShell logic ───────────────────────────────────────────────
set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%setup_tailscale.ps1"

if not exist "%PS_SCRIPT%" (
    echo ERROR: setup_tailscale.ps1 not found at %PS_SCRIPT%
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
pause
