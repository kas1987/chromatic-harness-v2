param(
    [string]$RepoRoot = "",
    [switch]$Remove,
    [switch]$CurrentHostOnly
)
$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
$RepoRoot = (Resolve-Path $RepoRoot).Path
$GuardScript = Join-Path $RepoRoot "scripts\session_unified_guard.py"
if (-not (Test-Path $GuardScript)) {
    throw "Missing script: $GuardScript"
}

$targetProfiles = @()
if ($CurrentHostOnly) {
    $targetProfiles += $PROFILE.CurrentUserCurrentHost
} else {
    $documents = [Environment]::GetFolderPath("MyDocuments")
    $targetProfiles += (Join-Path $documents "PowerShell\Microsoft.PowerShell_profile.ps1")
    $targetProfiles += (Join-Path $documents "WindowsPowerShell\Microsoft.PowerShell_profile.ps1")
}
$targetProfiles = $targetProfiles | Where-Object { $_ } | Select-Object -Unique

$start = "# >>> chromatic-session-guard >>>"
$end = "# <<< chromatic-session-guard <<<"

$snippetTemplate = @'
__START__
try {
    if (
        (Test-Path "__GUARD__") -and
        (Test-Path "__REPO__") -and
        -not $env:CHROMATIC_PROFILE_GUARD_RAN
    ) {
        $env:CHROMATIC_PROFILE_GUARD_RAN = "1"
        Push-Location "__REPO__"
        python "scripts/session_unified_guard.py" --surface cli --invoked-by automation | Out-Null
        Pop-Location
    }
} catch {
    Write-Warning "Chromatic session guard startup failed: $($_.Exception.Message)"
}
__END__
'@
$snippet = $snippetTemplate.Replace("__START__", $start).Replace("__END__", $end).Replace("__GUARD__", $GuardScript).Replace("__REPO__", $RepoRoot)

$pattern = [regex]::Escape($start) + ".*?" + [regex]::Escape($end)

foreach ($profilePath in $targetProfiles) {
    $profileDir = Split-Path -Parent $profilePath
    if (-not (Test-Path $profileDir)) {
        New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
    }
    if (-not (Test-Path $profilePath)) {
        New-Item -ItemType File -Path $profilePath -Force | Out-Null
    }

    $content = Get-Content -Raw -Path $profilePath -ErrorAction SilentlyContinue
    if ($null -eq $content) {
        $content = ""
    }

    if ($Remove) {
        $updated = [regex]::Replace($content, $pattern, "", [System.Text.RegularExpressions.RegexOptions]::Singleline)
        Set-Content -Path $profilePath -Value $updated -Encoding UTF8
        Write-Host "Removed Chromatic session guard profile block from: $profilePath"
        continue
    }

    if ([regex]::IsMatch($content, $pattern, [System.Text.RegularExpressions.RegexOptions]::Singleline)) {
        $updated = [regex]::Replace($content, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $snippet }, [System.Text.RegularExpressions.RegexOptions]::Singleline)
    } else {
        if ($content -and -not $content.EndsWith("`n")) { $content += "`r`n" }
        $updated = $content + $snippet + "`r`n"
    }

    Set-Content -Path $profilePath -Value $updated -Encoding UTF8
    Write-Host "Installed Chromatic session guard profile block in: $profilePath"
}

if (-not $Remove) {
    Write-Host "Open a new PowerShell terminal to activate it."
}
