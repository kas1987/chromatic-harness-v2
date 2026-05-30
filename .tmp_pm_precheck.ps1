$ErrorActionPreference='SilentlyContinue'
function Out-Line([string]$p,[string]$k,[string]$v){ if($null -eq $v){$v=''}; $v=($v -replace "`r|`n",' ') -replace '\s+',' '; Write-Output ("$p $k=$v") }
function Out-Warn([string]$m){ if($null -eq $m){$m=''}; $m=($m -replace "`r|`n",' ') -replace '\s+',' '; Write-Output ("PM_WARN $m") }

Out-Line 'PM_PRECHECK' 'cwd' ((Get-Location).Path)
$gitDir = (git rev-parse --git-dir 2>&1 | Select-Object -First 1)
$gitDirOk = ($LASTEXITCODE -eq 0)
Out-Line 'PM_PRECHECK' 'git_dir_ok' ($gitDirOk.ToString().ToLower())
Out-Line 'PM_DATA' 'git_dir' $gitDir
$gitHead = (git log -1 --oneline 2>&1 | Select-Object -First 1)
Out-Line 'PM_DATA' 'git_head' $gitHead

$chainPath = '.agents/ao/chain.jsonl'
$chainExists = Test-Path $chainPath
Out-Line 'PM_DATA' 'chain_exists' ($chainExists.ToString().ToLower())
$entries = @()
if($chainExists){ Get-Content $chainPath | ForEach-Object { $ln=$_.Trim(); if($ln){ try { $entries += ($ln | ConvertFrom-Json) } catch {} } } }
$phaseVals = @()
foreach($e in $entries){ if($e.PSObject.Properties.Name -contains 'phase'){ $phaseVals += ([string]$e.phase).ToLower() } elseif($e.PSObject.Properties.Name -contains 'name'){ $phaseVals += ([string]$e.name).ToLower() } }
function Phase-Present([string]$p){ return ($phaseVals | Where-Object { $_ -eq $p }).Count -gt 0 }
Out-Line 'PM_DATA' 'phase_research_present' ((Phase-Present 'research').ToString().ToLower())
Out-Line 'PM_DATA' 'phase_plan_present' ((Phase-Present 'plan').ToString().ToLower())
Out-Line 'PM_DATA' 'phase_premortem_present' ((($phaseVals | Where-Object { $_ -match 'pre-?mortem' }).Count -gt 0).ToString().ToLower())
Out-Line 'PM_DATA' 'phase_implement_or_crank_present' ((($phaseVals | Where-Object { $_ -eq 'implement' -or $_ -eq 'crank' }).Count -gt 0).ToString().ToLower())
Out-Line 'PM_DATA' 'phase_vibe_present' ((Phase-Present 'vibe').ToString().ToLower())
function Phase-Locked([string]$match){
  $subset = @($entries | Where-Object {
    $ph=''; if($_.PSObject.Properties.Name -contains 'phase'){ $ph=[string]$_.phase } elseif($_.PSObject.Properties.Name -contains 'name'){ $ph=[string]$_.name }
    $ph=$ph.ToLower(); if($match -eq 'premortem'){ return ($ph -match 'pre-?mortem') }; if($match -eq 'implement_or_crank'){ return ($ph -eq 'implement' -or $ph -eq 'crank') }; return ($ph -eq $match)
  })
  if($subset.Count -eq 0){ return $false }
  foreach($x in $subset){
    $locked=$false
    if($x.PSObject.Properties.Name -contains 'locked' -and $x.locked -eq $true){$locked=$true}
    if(-not $locked -and $x.PSObject.Properties.Name -contains 'status'){ $s=([string]$x.status).ToLower(); if($s -match 'locked|done|complete'){ $locked=$true } }
    if(-not $locked -and $x.PSObject.Properties.Name -contains 'state'){ $s=([string]$x.state).ToLower(); if($s -match 'locked|done|complete'){ $locked=$true } }
    if($locked){ return $true }
  }
  return $false
}
Out-Line 'PM_DATA' 'phase_research_locked' ((Phase-Locked 'research').ToString().ToLower())
Out-Line 'PM_DATA' 'phase_plan_locked' ((Phase-Locked 'plan').ToString().ToLower())
Out-Line 'PM_DATA' 'phase_premortem_locked' ((Phase-Locked 'premortem').ToString().ToLower())
Out-Line 'PM_DATA' 'phase_implement_or_crank_locked' ((Phase-Locked 'implement_or_crank').ToString().ToLower())
Out-Line 'PM_DATA' 'phase_vibe_locked' ((Phase-Locked 'vibe').ToString().ToLower())

$councilDir = '.agents/council'
$pmFile = Get-ChildItem $councilDir -File -Filter '*pre-mortem*.md' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$vibeFile = Get-ChildItem $councilDir -File -Filter '*vibe*.md' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
function Find-FailVerdict($f){ if(-not $f){ return '' }; $i=0; foreach($line in Get-Content $f.FullName){ $i++; if($line -match '^## Council Verdict:.*FAIL'){ return "$($f.FullName):$i" } }; return '' }
$pmFail = Find-FailVerdict $pmFile
$vibeFail = Find-FailVerdict $vibeFile
Out-Line 'PM_DATA' 'council_premortem_latest' (if($pmFile){$pmFile.FullName}else{'absent'})
Out-Line 'PM_DATA' 'council_vibe_latest' (if($vibeFile){$vibeFile.FullName}else{'absent'})
Out-Line 'PM_DATA' 'council_premortem_fail_ref' (if($pmFail){$pmFail}else{'none'})
Out-Line 'PM_DATA' 'council_vibe_fail_ref' (if($vibeFail){$vibeFail}else{'none'})

$missingArtifacts = New-Object System.Collections.Generic.List[string]
foreach($e in $entries){ foreach($prop in $e.PSObject.Properties){ $k=$prop.Name.ToLower(); $v=$prop.Value; if($v -is [string] -and $k -match 'path|artifact|output'){ $p=[string]$v; if($p -match '[\\/]' -or $p -match '\.[a-zA-Z0-9]{1,8}$'){ if(-not (Test-Path $p)){ $missingArtifacts.Add($p) } } } } }
$uniqMissing = $missingArtifacts | Select-Object -Unique
Out-Line 'PM_DATA' 'chain_missing_artifacts_count' ([string]($uniqMissing.Count))
if($uniqMissing.Count -gt 0){ Out-Warn ("chain_missing_artifacts=" + (($uniqMissing | Select-Object -First 5) -join ',')) }

$epicId = $env:EPIC_ID
if([string]::IsNullOrWhiteSpace($epicId)){ Out-Line 'PM_DATA' 'idempotency' 'skip-no-epic' } else { Out-Line 'PM_DATA' 'idempotency' 'epic-present' }

$bdOut = (bd list --status closed --since "7 days ago" 2>&1 | Select-Object -First 5)
Out-Line 'PM_DATA' 'bd_closed_head' (($bdOut -join ' || '))
$git7 = (git log --oneline --since="7 days ago" 2>&1 | Select-Object -First 10)
Out-Line 'PM_DATA' 'git_log_7d_head' (($git7 -join ' || '))

$rpiPath = '.agents/rpi/rpi-state.json'
if(Test-Path $rpiPath){
  try {
    $rpi = Get-Content -Raw $rpiPath | ConvertFrom-Json
    $streak = if($rpi.PSObject.Properties.Name -contains 'streak'){ $rpi.streak } elseif($rpi.PSObject.Properties.Name -contains 'current_streak'){ $rpi.current_streak } else { 'na' }
    $session = if($rpi.PSObject.Properties.Name -contains 'session'){ $rpi.session } elseif($rpi.PSObject.Properties.Name -contains 'session_id'){ $rpi.session_id } else { 'na' }
    $verdict = if($rpi.PSObject.Properties.Name -contains 'verdict_summary'){ $rpi.verdict_summary } elseif($rpi.PSObject.Properties.Name -contains 'verdict'){ $rpi.verdict } else { 'na' }
    Out-Line 'PM_DATA' 'rpi_streak' ([string]$streak)
    Out-Line 'PM_DATA' 'rpi_session' ([string]$session)
    Out-Line 'PM_DATA' 'rpi_verdict_summary' ([string]$verdict)
  } catch { Out-Warn 'rpi_state_unparseable' }
} else { Out-Warn 'rpi_state_absent' }

$latestPlan = Get-ChildItem -Recurse -File -Include '*plan*.md' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$latestResearch = Get-ChildItem -Recurse -File -Include '*research*.md' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$latestP2 = Get-ChildItem -Recurse -File -Include '*phase-2*summary*','*phase2*summary*' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Out-Line 'PM_DATA' 'latest_plan_doc' (if($latestPlan){$latestPlan.FullName}else{'none'})
Out-Line 'PM_DATA' 'latest_research_doc' (if($latestResearch){$latestResearch.FullName}else{'none'})
Out-Line 'PM_DATA' 'latest_phase2_summary' (if($latestP2){$latestP2.FullName}else{'none'})

$changesRaw = git show --name-status --pretty=format: HEAD~9..HEAD 2>&1
$changed = New-Object System.Collections.Generic.List[string]
foreach($ln in $changesRaw){
  if($ln -match '^[AMCRT][0-9]*\s+(.+)$'){ $path=$Matches[1].Trim(); if($path -match '\s+'){ $parts=$path -split '\s+'; $path=$parts[-1] }; if($path){$changed.Add($path)} }
}
$changedUnique = $changed | Select-Object -Unique
$missing = @($changedUnique | Where-Object { -not (Test-Path $_) })
Out-Line 'PM_DATA' 'changed_files_last10_count' ([string]($changedUnique.Count))
Out-Line 'PM_DATA' 'changed_missing_on_disk_count' ([string]($missing.Count))
if($missing.Count -gt 0){ Out-Warn ("changed_missing_on_disk=" + (($missing | Select-Object -First 5) -join ',')) }

$mdChanged = @($changedUnique | Where-Object { $_.ToLower().EndsWith('.md') -and (Test-Path $_) })
$broken = New-Object System.Collections.Generic.List[string]
$linkRegex = '\[[^\]]+\]\(([^)]+)\)'
foreach($md in $mdChanged){
  $base = Split-Path -Parent $md
  $lines = Get-Content $md
  $ln=0
  foreach($line in $lines){
    $ln++
    $ms = [regex]::Matches($line,$linkRegex)
    foreach($m in $ms){
      $t = $m.Groups[1].Value.Trim()
      if(-not $t -or $t.StartsWith('http://') -or $t.StartsWith('https://') -or $t.StartsWith('mailto:') -or $t.StartsWith('#')){ continue }
      $t = ($t -split '#')[0]
      if(-not $t){ continue }
      $cand = if([System.IO.Path]::IsPathRooted($t)){ $t } else { Join-Path $base $t }
      if(-not (Test-Path $cand)){ $broken.Add("${md}:$ln->$t") }
    }
  }
}
Out-Line 'PM_DATA' 'broken_md_links_count' ([string]($broken.Count))
if($broken.Count -gt 0){ Out-Warn ("broken_md_links=" + (($broken | Select-Object -First 5) -join ',')) }

$pytestOut = python -m pytest tests/test_session_closeout.py -q 2>&1
$pytestCode = $LASTEXITCODE
Out-Line 'PM_DATA' 'tests_last_known' 'passing_from_terminal_history'
Out-Line 'PM_DATA' 'smoke_pytest_exit' ([string]$pytestCode)
Out-Line 'PM_DATA' 'smoke_pytest_tail' (($pytestOut | Select-Object -Last 2) -join ' || ')

$docsExamplesChanged = (($changedUnique | Where-Object { $_ -match '^(docs|examples)[/\\]' -or $_ -match 'proof' }).Count -gt 0)
Out-Line 'PM_DATA' 'docs_examples_or_proof_changed_last10' ($docsExamplesChanged.ToString().ToLower())
Out-Line 'PM_DATA' 'gov_latest_json_exists' ((Test-Path '07_LOGS_AND_AUDIT/governance_intelligence/latest.json').ToString().ToLower())
Out-Line 'PM_DATA' 'closeout_telemetry_latest_exists' ((Test-Path '.agents/handoffs/closeout_telemetry_latest.json').ToString().ToLower())
