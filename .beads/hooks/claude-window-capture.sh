#!/usr/bin/env bash
# claude-window-capture.sh — SessionStart hook
# Captures the foreground window PID the moment this session opens.
# Written to ~/.agents/registry/claude-window-pid.txt for use by rpi-autolaunch.
# Best-effort: always exits 0.
set -euo pipefail

OUT_FILE="${HOME}/.agents/registry/claude-window-pid.txt"
mkdir -p "$(dirname "$OUT_FILE")"

# Use PowerShell to get the foreground window PID via Win32 API
PID_VAL=$(powershell.exe -NonInteractive -NoProfile -Command '
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinFg {
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
}
"@
$hwnd = [WinFg]::GetForegroundWindow()
$pid = 0u
[WinFg]::GetWindowThreadProcessId($hwnd, [ref]$pid) | Out-Null
Write-Output $pid
' 2>/dev/null || true)

# Strip whitespace / BOM
PID_VAL=$(printf '%s' "$PID_VAL" | tr -d '[:space:]\r\n\xef\xbb\xbf')

# Validate: must be a positive integer
if [[ "$PID_VAL" =~ ^[1-9][0-9]*$ ]]; then
    printf '%s\n' "$PID_VAL" > "$OUT_FILE"
fi

exit 0
