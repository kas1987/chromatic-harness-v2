#!/usr/bin/env bash
# session-health.sh — SessionStart hook: catch broken state before session begins
# Always exits 0 (fail-open)
# Safety rail: circuit-breaker wrapped, fast zombie kill, self-health output
set -u

# ── Circuit breaker integration ─────────────────────────────────────────────
CB_DIR="${HOME}/.claude/.agents/circuit-breaker"
mkdir -p "${CB_DIR}" 2>/dev/null || true
SH_FAIL_FILE="${CB_DIR}/session-health.failures"

LOG_DIR="${HOME}/.claude/.agents/router"
mkdir -p "${LOG_DIR}" 2>/dev/null || true

timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null)

# ── Zombie cleaner: kill orphaned bd show processes from prior sessions ────────
# FAST path: single PowerShell call kills ALL matching PIDs at once.
# Fallback: if PowerShell unavailable, try taskkill from bash.
zombie_count=0
if command -v powershell.exe &>/dev/null; then
  # Single invocation — find AND kill in one PS call via temp script (avoids escaping hell)
  _ps_script=$(mktemp /tmp/sh-zombie-XXXXXX.ps1 2>/dev/null || echo /tmp/sh-zombie-$$.ps1)
  cat > "$_ps_script" <<'PSEOF'
    $procs = Get-WmiObject Win32_Process -Filter "Name='node.exe'" |
      Where-Object { $_.CommandLine -match 'bd\.js show' }
    $count = 0
    if ($procs) {
      $procs | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        $count++
      }
    }
    Write-Output $count
PSEOF
  zombie_result=$(timeout 5 powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w "$_ps_script" 2>/dev/null || echo "$_ps_script")" 2>/dev/null | tr -d '\r')
  rm -f "$_ps_script" 2>/dev/null || true
  zombie_count=$(echo "$zombie_result" | grep -oE '[0-9]+' | tail -1)
  zombie_count=${zombie_count:-0}
  # Safety: clamp to reasonable range
  [ "$zombie_count" -gt 50 ] && zombie_count=0
  if [ "$zombie_count" -gt 0 ]; then
    printf '[SESSION-HEALTH] Cleaned %s orphaned bd-show zombie(s)\n' "$zombie_count" >&2
  fi
elif command -v taskkill.exe &>/dev/null; then
  # Fallback: tasklist + taskkill without PowerShell
  for pid in $(tasklist.exe /FI "IMAGENAME eq node.exe" /FO CSV /NH 2>/dev/null | grep -oP '^"node\.exe","\K[0-9]+' ); do
    taskkill.exe /PID "$pid" /F >/dev/null 2>&1 || true
    zombie_count=$(( zombie_count + 1 ))
  done
fi

# gh auth check (with timeout guard)
gh_status="fail"
if timeout 3 gh auth status >/dev/null 2>&1; then
  gh_status="ok"
fi

# bd CLI check (with timeout guard)
bd_status="fail"
if timeout 3 bd version >/dev/null 2>&1; then
  bd_status="ok"
fi

# secret scan: look for raw GitHub PAT in settings.json
secret_status="clean"
settings_file="${HOME}/.claude/settings.json"
if [ -f "${settings_file}" ] && grep -qE 'ghp_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]+' "${settings_file}" 2>/dev/null; then
  secret_status="warn"
fi

# multica daemon check (with timeout guard)
multica_status="fail"
_MCMD="${MULTICA_BIN:-$HOME/.multica/bin/multica}"
[ ! -f "$_MCMD" ] && _MCMD="multica"
if [ -f "${MULTICA_BIN:-$HOME/.multica/bin/multica}" ] || command -v multica &>/dev/null; then
  if timeout 3 "$_MCMD" daemon status 2>/dev/null | grep -q "running"; then
    multica_status="ok"
  else
    multica_status="stopped"
  fi
fi

# codex-team backend check — verify Codex CLI for multi-task dispatch path
codex_team_status="fail"
if command -v codex &>/dev/null; then
  codex_team_status="cli"
elif command -v spawn_agent &>/dev/null; then
  codex_team_status="sub-agent"
fi

# Ollama tier-0 routing health (referenced in audit findings C1-D / mc-qwn)
ollama_status_file="${LOG_DIR}/ollama-status.json"
tier0_degraded="false"

# First try a live curl probe (1s timeout); fall back to cached status file
if command -v curl &>/dev/null; then
  if ! curl -sf --max-time 1 "http://localhost:11434/api/tags" >/dev/null 2>&1; then
    tier0_degraded="true"
    # Write/update the status file so model-router.sh sees the current state
    printf '{"up":false,"checked_at":"%s","source":"session-health-curl"}\n' \
      "${timestamp}" > "${ollama_status_file}" 2>/dev/null || true
  else
    # Ollama is reachable — record up state
    printf '{"up":true,"checked_at":"%s","source":"session-health-curl"}\n' \
      "${timestamp}" > "${ollama_status_file}" 2>/dev/null || true
  fi
elif [ -f "${ollama_status_file}" ]; then
  # No curl available — fall back to pre-written status file
  if grep -q '"up":[[:space:]]*false' "${ollama_status_file}" 2>/dev/null; then
    tier0_degraded="true"
  fi
fi

# Reset the bump counter on session start so each session gets a fresh cap
BUMP_COUNT_FILE="${LOG_DIR}/tier0-bump-count.txt"
printf '0\n' > "${BUMP_COUNT_FILE}" 2>/dev/null || true

# router integrity check (fast — no subprocesses, just file/syntax checks)
router_status="ok"
_patterns="${HOME}/.claude/config/router-patterns.json"
_tiers="${HOME}/.claude/config/provider-tiers.json"
_hook="${HOME}/.claude/hooks/model-router.sh"
_settings="${HOME}/.claude/settings.json"
if ! jq -e '.tier_patterns' "${_patterns}" >/dev/null 2>&1; then
  router_status="patterns_invalid"
elif ! jq -e '.tiers' "${_tiers}" >/dev/null 2>&1; then
  router_status="tiers_invalid"
elif ! bash -n "${_hook}" 2>/dev/null; then
  router_status="hook_syntax_error"
elif ! jq -e '.hooks.PreToolUse[]? | select(.matcher=="Agent") | .hooks[]? | select(.command | test("model-router"))' \
     "${_settings}" >/dev/null 2>&1; then
  router_status="hook_not_wired"
fi

# Write JSON status
jq -cn \
  --arg ts "${timestamp}" \
  --arg gh "${gh_status}" \
  --arg bd "${bd_status}" \
  --arg sec "${secret_status}" \
  --arg multica "${multica_status}" \
  --arg codex_team "${codex_team_status}" \
  --argjson tier0_degraded "${tier0_degraded}" \
  --arg router "${router_status}" \
  '{checked_at: $ts, gh_auth: $gh, bd: $bd, secret_scan: $sec, multica_daemon: $multica, codex_team: $codex_team, tier0_degraded: $tier0_degraded, router: $router}' \
  > "${LOG_DIR}/session-health.json" 2>/dev/null || true

# Append human-readable log line
printf '[%s] gh=%s bd=%s secrets=%s multica=%s codex_team=%s tier0_degraded=%s router=%s\n' \
  "${timestamp}" "${gh_status}" "${bd_status}" "${secret_status}" "${multica_status}" "${codex_team_status}" "${tier0_degraded}" "${router_status}" \
  >> "${LOG_DIR}/session-health.log" 2>/dev/null || true

# Emit operator-visible WARN banner on tier-0 degradation
if [ "${tier0_degraded}" = "true" ]; then
  printf '[SESSION-HEALTH] WARN: Ollama offline — tier-0 routing degraded, cloud bump uncapped\n' >&2
fi

# Emit WARN if router is broken
if [ "${router_status}" != "ok" ]; then
  printf '[SESSION-HEALTH] WARN: Router broken (%s) — all Agent dispatches will hit Sonnet T4\n' "${router_status}" >&2
fi

# Emit WARN if raw PAT detected in settings.json
if [ "${secret_status}" = "warn" ]; then
  printf '[SESSION-HEALTH] WARN: Raw GitHub PAT detected in settings.json — move to GITHUB_PERSONAL_ACCESS_TOKEN_PATH file reference\n' >&2
fi

# ── Self-health: write circuit-breaker status ──────────────────────────────
printf '0' > "${SH_FAIL_FILE}" 2>/dev/null || true

exit 0
