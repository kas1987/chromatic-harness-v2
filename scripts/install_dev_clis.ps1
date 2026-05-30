#Requires -Version 5.1
<#
.SYNOPSIS
  Install and verify CLIs for the Chromatic workspace (all local repos).

.DESCRIPTION
  Reads config/dev_cli_manifest.yaml, installs missing tools via winget/npm/beads,
  installs Python/Node deps per repo, and prints an audit table.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/install_dev_clis.ps1
  powershell -File scripts/install_dev_clis.ps1 -AuditOnly
  powershell -File scripts/install_dev_clis.ps1 -SkipWinget
#>
param(
    [switch] $AuditOnly,
    [switch] $SkipWinget,
    [switch] $SkipPython,
    [switch] $SkipNode,
    [switch] $Force
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Expand-HomePath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
    if ($Path -eq '~') { return $env:USERPROFILE }
    if ($Path -match '^~[/\\](.+)$') { return Join-Path $env:USERPROFILE $matches[1] }
    return $Path
}

function Get-CommandPath {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Read-Manifest {
    $manifestPath = Join-Path $RepoRoot 'config/dev_cli_manifest.yaml'
    if (-not (Test-Path $manifestPath)) {
        throw "Missing manifest: $manifestPath"
    }
    $json = python -c "import yaml,json,sys; print(json.dumps(yaml.safe_load(open(sys.argv[1],encoding='utf-8'))))" $manifestPath
    if ($LASTEXITCODE -ne 0) { throw 'Failed to parse dev_cli_manifest.yaml (need PyYAML: pip install pyyaml)' }
    return $json | ConvertFrom-Json
}

function Install-Beads {
    if (Get-CommandPath 'bd') { return }
    Write-Host '  Installing beads (bd) via official install.ps1 ...'
    try {
        irm https://raw.githubusercontent.com/gastownhall/beads/main/install.ps1 | iex
    } catch {
        Write-Warning "beads install.ps1 failed: $_"
        if (Get-CommandPath 'go') {
            Write-Host '  Fallback: go install beads ...'
            go install github.com/steveyegge/beads/cmd/bd@latest
        }
    }
}

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}

function Test-IsRequired {
    param($Value)
    return ($Value -eq $true) -or ($Value -eq 'true') -or ($Value -eq 'required')
}

function Test-IsRecommended {
    param($Value)
    return ($Value -eq 'recommended')
}

function Test-AuthHints {
    if (Get-CommandPath 'gh') {
        gh auth status 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'gh not authenticated - run: gh auth login'
        }
    }
    if (Get-CommandPath 'gk') {
        gk version 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'gk present but may need auth - run: gk auth login'
        }
    }
}

$manifest = Read-Manifest
$results = @()

Write-Host "`n=== Chromatic dev CLI install ===`n"

foreach ($tool in $manifest.tools) {
    $path = Get-CommandPath $tool.test
    $status = if ($path) { 'OK' } else { 'MISSING' }

    if (-not $path -and -not $AuditOnly) {
        Write-Host "Installing missing tool: $($tool.name)"
        $wingetId = $tool.PSObject.Properties['winget'].Value
        $npmGlobal = $tool.PSObject.Properties['npm_global'].Value
        $beadsInstall = $tool.PSObject.Properties['beads_install'].Value
        if ($beadsInstall) {
            Install-Beads
        } elseif ($wingetId) {
            if ($SkipWinget) {
                Write-Host "  skip winget ($($tool.name)) - SkipWinget"
            } else {
                Write-Host "  winget install $wingetId ..."
                winget install --id $wingetId -e --accept-package-agreements --accept-source-agreements | Out-Host
                if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) {
                    Write-Warning "winget install $wingetId exited $LASTEXITCODE"
                }
            }
        } elseif ($npmGlobal) {
            if (-not (Get-CommandPath 'npm')) {
                Write-Warning "npm missing; cannot install global $npmGlobal"
            } else {
                Write-Host "  npm install -g $npmGlobal ..."
                npm install -g $npmGlobal | Out-Host
            }
        }
        Refresh-Path
        $path = Get-CommandPath $tool.test
        $status = if ($path) { 'OK' } else { 'MISSING' }
    }

    $results += [PSCustomObject]@{
        Tool     = $tool.name
        Required = $tool.required
        Status   = $status
        Path     = if ($path) { $path } else { '' }
        Note     = $tool.note
    }
}

if (-not $AuditOnly) {
    Refresh-Path
    if (-not $SkipPython) {
        Write-Host "`n=== Python dependencies ===`n"
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        foreach ($repoName in $manifest.repos.PSObject.Properties.Name) {
            $repo = $manifest.repos.$repoName
            $repoPath = Expand-HomePath ([string]$repo.PSObject.Properties['path'].Value)
            if (-not $repo.PSObject.Properties['python_requirements'].Value) { continue }
            $requirements = [string]$repo.PSObject.Properties['python_requirements'].Value
            if ([string]::IsNullOrWhiteSpace($repoPath)) {
                Write-Host "  skip python deps for $repoName - path missing"
                continue
            }
            if (-not (Test-Path $repoPath)) {
                Write-Host "  skip python deps for $repoName - path missing: $repoPath"
                continue
            }
            $reqFile = Join-Path $repoPath $requirements
            if (-not (Test-Path $reqFile)) {
                Write-Host "  skip python deps for $repoName - no $requirements"
                continue
            }
            Write-Host "  pip install -r $reqFile ..."
            Push-Location $repoPath
            python -m pip install -q -r $requirements 2>&1 | Out-Null
            $pipExtras = $repo.PSObject.Properties['pip_extras'].Value
            if ($pipExtras) {
                python -m pip install -q @($pipExtras) 2>&1 | Out-Null
            }
            Pop-Location
        }
        Write-Host '  pip install harness dev extras (pytest-asyncio, ruff, mypy, bandit) ...'
        python -m pip install -q pytest-asyncio ruff mypy bandit 2>&1 | Out-Null
        $ErrorActionPreference = $prevEap
    }

    if (-not $SkipNode) {
        Write-Host "`n=== Node dependencies ===`n"
        foreach ($repoName in $manifest.repos.PSObject.Properties.Name) {
            $repo = $manifest.repos.$repoName
            if ($repo.PSObject.Properties['npm_install'].Value) {
                $nodeRepoPath = Expand-HomePath ([string]$repo.PSObject.Properties['path'].Value)
                if ([string]::IsNullOrWhiteSpace($nodeRepoPath) -or -not (Test-Path $nodeRepoPath)) {
                    Write-Host "  skip npm for $repoName - path missing: $nodeRepoPath"
                    continue
                }
                $pkg = Join-Path $nodeRepoPath 'package.json'
                if (-not (Test-Path $pkg)) { continue }
                if (-not (Get-CommandPath 'npm')) {
                    Write-Warning 'npm missing; cannot install Node deps'
                    continue
                }
                Write-Host "  npm install ($nodeRepoPath) ..."
                Push-Location $nodeRepoPath
                npm install --no-fund --no-audit
                Pop-Location
            }
        }
    }
}

Write-Host "`n=== CLI audit ===`n"
$results | Format-Table -AutoSize Tool, Required, Status, Path

$requiredMissing = @($results | Where-Object { (Test-IsRequired $_.Required) -and $_.Status -ne 'OK' })
$recommendedMissing = @($results | Where-Object { (Test-IsRecommended $_.Required) -and $_.Status -ne 'OK' })

if ($requiredMissing.Count -gt 0) {
    Write-Host "`nRequired tools still missing:"
    $requiredMissing | ForEach-Object { Write-Host "  - $($_.Tool)" }
}

if ($recommendedMissing.Count -gt 0) {
    Write-Host "`nRecommended tools still missing:"
    $recommendedMissing | ForEach-Object { Write-Host "  - $($_.Tool)" }
}

Test-AuthHints

if ($requiredMissing.Count -gt 0) {
    Write-Host "`nInstall incomplete (required tools missing)."
    exit 1
}

Write-Host "`nDev CLI install complete."
exit 0
