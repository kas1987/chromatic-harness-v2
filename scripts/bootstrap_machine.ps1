# bootstrap_machine.ps1
# Run once on any machine to register HARNESS_ROOT and verify the harness clone.
# Usage: powershell -File scripts\bootstrap_machine.ps1

$harness = Split-Path -Parent $PSScriptRoot

# Set HARNESS_ROOT as a persistent user env var
$current = [System.Environment]::GetEnvironmentVariable("HARNESS_ROOT", "User")
if ($current -ne $harness) {
    [System.Environment]::SetEnvironmentVariable("HARNESS_ROOT", $harness, "User")
    Write-Host "HARNESS_ROOT set to: $harness"
} else {
    Write-Host "HARNESS_ROOT already correct: $harness"
}

# Also set in current session
$env:HARNESS_ROOT = $harness

# Verify
$git = git -C $harness log --oneline -1 2>&1
Write-Host "Harness HEAD: $git"
Write-Host ""
Write-Host "Setup complete. Restart your shell to pick up HARNESS_ROOT in new sessions."
