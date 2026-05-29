# Initialize roach-pi git submodule for Option C runtime.
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not (Test-Path ".gitmodules")) {
    Write-Error ".gitmodules missing — run from chromatic-harness-v2 root"
}

Write-Host "Initializing submodule 02_RUNTIME/runtime-engines/roach-pi ..."
git submodule update --init --recursive 02_RUNTIME/runtime-engines/roach-pi

python scripts/roach_pi_status.py
Write-Host "Done. Adapter uses stub mode until health markers exist."
