$ErrorActionPreference = 'Stop'
$roots = @(
  'C:\Users\kas41',
  'C:\.01_Image Org',
  'C:\.04_Prism',
  'C:\fusion-computer'
)
$excludeFragments = @('\\.worktrees\\','\\node_modules\\','\\AppData\\','\\chat-session-resources\\')
$repoPaths = @()
foreach ($root in $roots) {
  if (-not (Test-Path -LiteralPath $root)) { continue }
  Get-ChildItem -LiteralPath $root -Directory -Filter '.git' -Recurse -Force -ErrorAction SilentlyContinue |
    ForEach-Object {
      $repoPath = $_.Parent.FullName
      $skip = $false
      foreach ($frag in $excludeFragments) {
        if ($repoPath -like "*$frag*") { $skip = $true; break }
      }
      if (-not $skip) { $repoPaths += $repoPath }
    }
}
$repoList = $repoPaths | Sort-Object -Unique
$discovered = @($repoList).Count
$initialized = 0
$alreadyIndexed = 0
$failed = 0
$processed = @()
$failures = @()
foreach ($repo in $repoList) {
  $processed += $repo
  Push-Location -LiteralPath $repo
  try {
    if (Test-Path -LiteralPath '.codegraph\\codegraph.db') {
      $out = & codegraph status . 2>&1
      if ($LASTEXITCODE -eq 0) { $alreadyIndexed++ }
      else {
        $failed++
        $lastErr = ($out | ForEach-Object { $_.ToString() } | Where-Object { $_.Trim() -ne '' } | Select-Object -Last 1)
        if (-not $lastErr) { $lastErr = 'Unknown error' }
        $failures += ("$repo :: $lastErr")
      }
    }
    else {
      $out = & codegraph init -i . 2>&1
      if ($LASTEXITCODE -eq 0) { $initialized++ }
      else {
        $failed++
        $lastErr = ($out | ForEach-Object { $_.ToString() } | Where-Object { $_.Trim() -ne '' } | Select-Object -Last 1)
        if (-not $lastErr) { $lastErr = 'Unknown error' }
        $failures += ("$repo :: $lastErr")
      }
    }
  }
  catch {
    $failed++
    $failures += ("$repo :: $($_.Exception.Message)")
  }
  finally {
    Pop-Location
  }
}
Write-Output "BULK_CG: discovered=$discovered"
Write-Output "BULK_CG: initialized=$initialized"
Write-Output "BULK_CG: already_indexed=$alreadyIndexed"
Write-Output "BULK_CG: failed=$failed"
$processed | Select-Object -First 15 | ForEach-Object { Write-Output "BULK_CG_REPO: $_" }
$failures | ForEach-Object { Write-Output "BULK_CG_FAIL: $_" }
