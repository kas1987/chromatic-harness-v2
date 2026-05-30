param(
    [string]$BaseRef = "HEAD",
    [switch]$Staged,
    [string]$Filter
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "git is required but was not found on PATH."
}

if (-not (Get-Command codegraph -ErrorAction SilentlyContinue)) {
    Write-Error "codegraph is required but was not found on PATH. Install with: npm install -g @colbymchenry/codegraph"
}

if (-not (Test-Path ".codegraph")) {
    Write-Host "[codegraph] .codegraph not found. Initializing and indexing this repo first..."
    codegraph init -i . | Out-Host
}

$changedFiles = @()
if ($Staged) {
    $changedFiles = git diff --name-only --cached
} else {
    $changedFiles = git diff --name-only $BaseRef
}

$changedFiles = $changedFiles |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
    Sort-Object -Unique

if (-not $changedFiles -or $changedFiles.Count -eq 0) {
    Write-Host "[codegraph] No changed files matched the selected git scope."
    exit 0
}

Write-Host "[codegraph] Changed files: $($changedFiles.Count)"
$changedFiles | ForEach-Object { Write-Host " - $_" }

$cgArgs = @("affected", "--stdin")
if ($Filter) {
    $cgArgs += @("--filter", $Filter)
}

$inputPayload = ($changedFiles -join "`n")
$inputPayload | codegraph @cgArgs
