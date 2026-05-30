# One-shot: Claude Code CLI production readiness for Chromatic Harness v2
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "=== Claude Harness production setup ===" -ForegroundColor Cyan

Write-Host "`n[1/6] Sync lite workflows to ~/.claude/workflows ..."
& "$PSScriptRoot\sync_claude_workflows.ps1"

Write-Host "`n[2/6] Slim global SessionStart hooks (Harness boot stays in project settings) ..."
python "$RepoRoot\scripts\slim_claude_global_hooks.py" --apply

Write-Host "`n[3/6] Context trim + bootstrap ..."
python "$RepoRoot\scripts\context_trim_audit.py" --root .
python "$RepoRoot\scripts\new_session_bootstrap.py" --root .

Write-Host "`n[4/6] Daily audit with report artifacts ..."
python "$RepoRoot\scripts\daily_harness_audit.py" --root . --report

Write-Host "`n[5/6] Claude harness validation ..."
python "$RepoRoot\scripts\validate_claude_harness.py" --root .

Write-Host "`n[6/6] Governance stack ..."
python "$RepoRoot\scripts\validate_governance_stack.py"

Write-Host "`nDone. Open Claude Code in this repo; SessionStart/End hooks are in .claude/settings.json" -ForegroundColor Green
