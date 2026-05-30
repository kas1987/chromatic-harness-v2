$ErrorActionPreference = "Stop"
$issuesPath = '.beads/issues.jsonl'
function Get-OpenMap {
  $map = @{}
  if (-not (Test-Path $issuesPath)) { return $map }
  Get-Content $issuesPath | ForEach-Object {
    $line = $_.Trim()
    if (-not $line) { return }
    try { $obj = $line | ConvertFrom-Json } catch { return }
    $title = [string]$obj.title; $id = [string]$obj.id
    if (-not $title -or -not $id) { return }
    $isClosed = $false
    if ($null -ne $obj.closed -and [bool]$obj.closed) { $isClosed = $true }
    if ($null -ne $obj.closed_at -and [string]$obj.closed_at) { $isClosed = $true }
    if ($obj.PSObject.Properties.Name -contains 'status') { if (([string]$obj.status).ToLowerInvariant() -match 'closed|done|resolved') { $isClosed = $true } }
    if ($obj.PSObject.Properties.Name -contains 'state') { if (([string]$obj.state).ToLowerInvariant() -match 'closed|done|resolved') { $isClosed = $true } }
    if (-not $isClosed -and -not $map.ContainsKey($title)) { $map[$title] = $id }
  }
  return $map
}
function Try-BdCreate([string]$Title,[string]$Type,[string]$Priority) {
  $attempts = @(
    @('create','--title',$Title,'--type',$Type,'--priority',$Priority),
    @('create',$Title,'--type',$Type,'--priority',$Priority),
    @('create','--title',$Title,'-t',$Type,'-p',$Priority),
    @('create',$Title,'-t',$Type,'-p',$Priority)
  )
  $lastErr = ''
  foreach ($args in $attempts) {
    $out = & bd @args 2>&1; $code = $LASTEXITCODE
    if ($code -eq 0) { return @{ ok = $true } }
    $msg = (($out | Select-Object -Last 1) -join ' ').Trim(); if (-not $msg) { $msg = "bd create failed (exit=$code)" }
    $lastErr = $msg
  }
  return @{ ok = $false; error = $lastErr }
}
function Ensure-Item([string]$Title,[string]$Type,[string]$Priority) {
  $openMap = Get-OpenMap
  if ($openMap.ContainsKey($Title)) { return @{ id = $openMap[$Title]; action = 'reused'; ok = $true } }
  $create = Try-BdCreate -Title $Title -Type $Type -Priority $Priority
  if (-not $create.ok) { return @{ id = ''; action = 'created'; ok = $false; error = [string]$create.error } }
  $openMap2 = Get-OpenMap
  if ($openMap2.ContainsKey($Title)) { return @{ id = $openMap2[$Title]; action = 'created'; ok = $true } }
  return @{ id = ''; action = 'created'; ok = $false; error = 'create succeeded but new open item was not found in .beads/issues.jsonl' }
}
$epicTitle = 'EPIC: Open TODO + Next Steps Backlog Capture (2026-05-30)'
$taskTitles = @(
'Policy: add schema/range validation for config/epic_swot_policy.json',
'Closeout: add --epic-policy-config override for alternate governance tuning',
'Telemetry: add historical closeout telemetry snapshots alongside latest',
'EPIC-SWOT governance: add staleness override for reused open epic',
'Router TODO: expose full prompt on RouteRequest',
'Provider selector TODO: detect Claude session context explicitly',
'Context detector TODO: compute memory_pressure from real system metrics',
'Roach adapter TODO: cleanup roach-pi resources after run',
'Roach adapter TODO: refresh confidence/security magnets from runtime signals'
)
$errors = New-Object System.Collections.Generic.List[string]
$epic = Ensure-Item -Title $epicTitle -Type 'epic' -Priority 'P2'
if (-not $epic.ok) { $errors.Add("ERROR=EPIC | $epicTitle | $($epic.error)") }
$taskResults = @()
foreach ($t in $taskTitles) {
  $res = Ensure-Item -Title $t -Type 'task' -Priority 'P2'
  $link = 'skipped'
  if (-not $res.ok) { $errors.Add("ERROR=TASK_CREATE | $t | $($res.error)") }
  if ($res.id -and $epic.id) {
    $linkOut = & bd update $res.id --parent $epic.id 2>&1; $linkCode = $LASTEXITCODE
    if ($linkCode -eq 0) { $link = 'linked' } else { $link = 'link-error'; $line = (($linkOut | Select-Object -Last 1) -join ' ').Trim(); if (-not $line) { $line = "bd update failed (exit=$linkCode)" }; $errors.Add("ERROR=TASK_LINK | $t | $line") }
  }
  $taskResults += [pscustomobject]@{ Title = $t; Id = [string]$res.id; Action = [string]$res.action; Link = $link }
}
"EPIC_ID=$($epic.id)"
"EPIC_ACTION=$($epic.action)"
foreach ($tr in $taskResults) { "TASK=$($tr.Title) | ID=$($tr.Id) | ACTION=$($tr.Action) | LINK=$($tr.Link)" }
foreach ($e in $errors) { $e }
