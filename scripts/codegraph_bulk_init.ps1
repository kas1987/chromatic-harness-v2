param(
  [string]$ReportPath = ".tmp_codegraph_bulk_report.csv"
)

$ErrorActionPreference = "Stop"

$roots = @(
  "C:\Users\kas41",
  "C:\.01_Image Org",
  "C:\.04_Prism",
  "C:\fusion-computer"
)

$excludeFragments = @(
  "\.worktrees\",
  "\node_modules\",
  "\AppData\",
  "\chat-session-resources\",
  "\.cargo\",
  "\.claude\plugins\cache\",
  "\temp_git_",
  "\.cache\"
)

$repoSet = New-Object System.Collections.Generic.HashSet[string] ([System.StringComparer]::OrdinalIgnoreCase)
foreach ($root in $roots) {
  if (-not (Test-Path -LiteralPath $root)) { continue }

  Get-ChildItem -LiteralPath $root -Directory -Filter ".git" -Recurse -Force -ErrorAction SilentlyContinue |
    ForEach-Object {
      $repoPath = $_.Parent.FullName
      if (-not $repoPath) { return }

      $skip = $false
      foreach ($frag in $excludeFragments) {
        if ($repoPath -like "*$frag*") {
          $skip = $true
          break
        }
      }

      if (-not $skip) {
        [void]$repoSet.Add($repoPath)
      }
    }
}

$repoList = @($repoSet) | Sort-Object
$initialized = 0
$alreadyIndexed = 0
$failed = @()
$processed = @()
$rows = @()

foreach ($repo in $repoList) {
  $processed += $repo

  if (-not (Test-Path -LiteralPath $repo)) {
    $failed += ("{0} :: repo path does not exist" -f $repo)
    $rows += [pscustomobject]@{
      repo   = $repo
      action = "skip-missing"
      status = "failed"
      detail = "repo path does not exist"
    }
    continue
  }

  Push-Location -LiteralPath $repo
  try {
    if (Test-Path -LiteralPath ".codegraph\\codegraph.db") {
      $out = & codegraph status . 2>&1
      if ($LASTEXITCODE -eq 0) {
        $alreadyIndexed++
        $rows += [pscustomobject]@{
          repo   = $repo
          action = "status"
          status = "ok"
          detail = "already indexed"
        }
      }
      else {
        $lastErr = ($out | ForEach-Object { $_.ToString() } | Where-Object { $_.Trim() -ne "" } | Select-Object -Last 1)
        if (-not $lastErr) { $lastErr = "Unknown error" }
        $failed += ("{0} :: {1}" -f $repo, $lastErr)
        $rows += [pscustomobject]@{
          repo   = $repo
          action = "status"
          status = "failed"
          detail = [string]$lastErr
        }
      }
    }
    else {
      $out = & codegraph init -i . 2>&1
      if ($LASTEXITCODE -eq 0) {
        $initialized++
        $rows += [pscustomobject]@{
          repo   = $repo
          action = "init"
          status = "ok"
          detail = "initialized"
        }
      }
      else {
        $lastErr = ($out | ForEach-Object { $_.ToString() } | Where-Object { $_.Trim() -ne "" } | Select-Object -Last 1)
        if (-not $lastErr) { $lastErr = "Unknown error" }
        $failed += ("{0} :: {1}" -f $repo, $lastErr)
        $rows += [pscustomobject]@{
          repo   = $repo
          action = "init"
          status = "failed"
          detail = [string]$lastErr
        }
      }
    }
  }
  catch {
    $failed += ("{0} :: {1}" -f $repo, $_.Exception.Message)
    $rows += [pscustomobject]@{
      repo   = $repo
      action = "exception"
      status = "failed"
      detail = $_.Exception.Message
    }
  }
  finally {
    Pop-Location
  }
}

$reportAbs = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $ReportPath))
$rows | Export-Csv -Path $reportAbs -NoTypeInformation -Encoding UTF8

Write-Output ("BULK_CG: discovered={0}" -f $repoList.Count)
Write-Output ("BULK_CG: initialized={0}" -f $initialized)
Write-Output ("BULK_CG: already_indexed={0}" -f $alreadyIndexed)
Write-Output ("BULK_CG: failed={0}" -f $failed.Count)
Write-Output ("BULK_CG: report={0}" -f $reportAbs)

$processed | Select-Object -First 15 | ForEach-Object { Write-Output ("BULK_CG_REPO: {0}" -f $_) }
$failed | ForEach-Object { Write-Output ("BULK_CG_FAIL: {0}" -f $_) }
