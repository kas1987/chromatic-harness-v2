#!/usr/bin/env bash
# model-router.sh v3 — 5-tier Agent call router (PreToolUse hook)
#
# Scores incoming Agent calls against tier_patterns from router-patterns.json.
# Emits additionalContext advisory or permissionDecision:deny for pure-LLM calls.
# Checks ollama-status.json; if Ollama is down, bumps tier-0 → tier-1.
#
# Tiers: 0=ollama 1=featherless 2=openai 3=gemini 4=claude(native)
# Exit codes: 0 always (fail-open)

set -u

LOG_DIR="${ROUTER_LOG_DIR:-${HOME}/.claude/.agents/router}"
LOG_FILE="${LOG_DIR}/log.jsonl"
PATTERNS_FILE="${ROUTER_PATTERNS_FILE:-${HOME}/.claude/config/router-patterns.json}"
TIERS_FILE="${ROUTER_TIERS_FILE:-${HOME}/.claude/config/provider-tiers.json}"
ROUTER_BLOCK_ENABLED="${ROUTER_BLOCK_ENABLED:-true}"

mkdir -p "${LOG_DIR}" 2>/dev/null || exit 0

# ---- Ollama liveness (read pre-written status file) ----
OLLAMA_STATUS_FILE="${LOG_DIR}/ollama-status.json"
ollama_up=true
if [ -f "${OLLAMA_STATUS_FILE}" ]; then
  _up=$(jq -r '.up' "${OLLAMA_STATUS_FILE}" 2>/dev/null)
  [ "${_up}" = "false" ] && ollama_up=false
fi

# ---- Read stdin ----
input=$(cat 2>/dev/null) || exit 0
[ -z "${input}" ] && exit 0

# Only act on Agent tool calls
tool_name=$(printf '%s' "${input}" | jq -r '.tool_name // ""' 2>/dev/null) || exit 0
[ "${tool_name}" != "Agent" ] && exit 0

description=$(printf '%s' "${input}" | jq -r '.tool_input.description // ""' 2>/dev/null)
prompt=$(printf '%s' "${input}" | jq -r '.tool_input.prompt // ""' 2>/dev/null)
sub_type=$(printf '%s' "${input}" | jq -r '.tool_input.subagent_type // "general-purpose"' 2>/dev/null)
model=$(printf '%s' "${input}" | jq -r '.tool_input.model // ""' 2>/dev/null)

# Combined haystack
haystack=$(printf '%s\n%s' "${description}" "${prompt}" | tr '[:upper:]' '[:lower:]')

# ---- 5-tier scoring ----
best_tier=4
best_score=0
reason="default: no pattern matched"

if [ -r "${PATTERNS_FILE}" ] && jq -e '.tier_patterns' "${PATTERNS_FILE}" >/dev/null 2>&1; then
  for tier in 0 1 2 3 4; do
    score=0
    while IFS= read -r pattern; do
      [ -z "${pattern}" ] && continue
      if printf '%s' "${haystack}" | grep -Eqi "${pattern}"; then
        score=$(( score + 1 ))
      fi
    done < <(jq -r --argjson t "${tier}" '.tier_patterns[$t | tostring][]?' "${PATTERNS_FILE}" 2>/dev/null | tr -d '\r')
    if [ "${score}" -gt "${best_score}" ]; then
      best_score=${score}
      best_tier=${tier}
      reason="tier-${tier}: ${score} pattern(s) matched"
    fi
  done
fi

# ---- Ollama-down bump: tier-0 → tier-1 ----
BUMP_COUNT_FILE="${LOG_DIR}/tier0-bump-count.txt"
TIER0_BUMP_CAP="${TIER0_BUMP_CAP:-10}"

if [ "${ollama_up}" = "false" ] && [ "${best_tier}" -eq 0 ]; then
  best_tier=1
  reason="ollama-down: promoted tier 0→1 (featherless); ${reason}"

  # Auto-reset bump counter if the file is stale (>24h old)
  if [ -f "${BUMP_COUNT_FILE}" ]; then
    stale=$(find "${BUMP_COUNT_FILE}" -mmin +1440 2>/dev/null)
    if [ -n "${stale}" ]; then
      printf '0\n' > "${BUMP_COUNT_FILE}" 2>/dev/null || true
    fi
  fi

  # Increment and read bump counter
  current_count=0
  if [ -f "${BUMP_COUNT_FILE}" ]; then
    current_count=$(cat "${BUMP_COUNT_FILE}" 2>/dev/null | tr -dc '0-9')
    current_count="${current_count:-0}"
  fi
  new_count=$(( current_count + 1 ))
  printf '%s\n' "${new_count}" > "${BUMP_COUNT_FILE}" 2>/dev/null || true

  # Emit WARNING when cap is reached or exceeded
  if [ "${new_count}" -gt "${TIER0_BUMP_CAP}" ]; then
    printf '[MODEL-ROUTER] WARN: Tier-0 bump cap reached (%s/%s). Further bumps continue but flag cost risk.\n' \
      "${new_count}" "${TIER0_BUMP_CAP}" >&2
  fi
fi

# ---- Model override shortcuts ----
# Explicit Claude model aliases: haiku caps at tier-1, sonnet/opus always tier-4
if [ "${model}" = "haiku" ] && [ "${best_tier}" -gt 1 ]; then
  best_tier=1
  reason="caller specified haiku → capped at tier-1"
fi
if [ "${model}" = "sonnet" ]; then
  best_tier=4
  reason="caller specified sonnet → tier-4 (native claude)"
fi
if [ "${model}" = "opus" ]; then
  best_tier=4
  reason="caller specified opus → tier-4 (native claude)"
fi

# ---- subagent_type tier boost (read from patterns file) ----
if [ -r "${PATTERNS_FILE}" ]; then
  _boost=$(jq -r --arg st "${sub_type}" '.subagent_type_boost[$st] // 0' "${PATTERNS_FILE}" 2>/dev/null)
  if [ -n "${_boost}" ] && [ "${_boost}" != "null" ] && [ "${_boost}" != "0" ]; then
    new_tier=$(( best_tier + _boost ))
    [ "${new_tier}" -lt 0 ] && new_tier=0
    [ "${new_tier}" -gt 4 ] && new_tier=4
    if [ "${new_tier}" -ne "${best_tier}" ]; then
      best_tier=${new_tier}
      reason="${reason} [subagent_type=${sub_type} boost=${_boost}]"
    fi
  fi
fi

# ---- Active-skill floor (mc-6a5.2) ----
# If skill-tier-tracker wrote a recent active-skill.json, use model_tier as floor.
# Floor prevents agents from being routed below the invoking skill's declared tier.
# Caller explicit model (haiku/sonnet/opus) already resolved above — floor only fires on unspecified model.
ACTIVE_SKILL_FILE="${LOG_DIR}/active-skill.json"
if [ -z "${model}" ] && [ -f "${ACTIVE_SKILL_FILE}" ]; then
  now_epoch=$(date +%s 2>/dev/null)
  expires_at=$(jq -r '.expires_at_epoch // 0' "${ACTIVE_SKILL_FILE}" 2>/dev/null)
  skill_tier=$(jq -r '.tier_num // -1' "${ACTIVE_SKILL_FILE}" 2>/dev/null)
  active_skill=$(jq -r '.skill // ""' "${ACTIVE_SKILL_FILE}" 2>/dev/null)
  if [ "${now_epoch}" -le "${expires_at}" ] && [ "${skill_tier}" -ge 0 ] 2>/dev/null; then
    if [ "${skill_tier}" -gt "${best_tier}" ]; then
      best_tier=${skill_tier}
      reason="${reason} [skill-floor: ${active_skill} declared tier-${skill_tier}]"
    fi
  fi
fi

# ---- Resolve provider/model from tiers config ----
target_provider="claude"
target_model="claude-sonnet-4-6"
if [ -r "${TIERS_FILE}" ]; then
  _p=$(jq -r --argjson t "${best_tier}" '.tiers[$t | tostring].primary.provider // ""' "${TIERS_FILE}" 2>/dev/null)
  _m=$(jq -r --argjson t "${best_tier}" '.tiers[$t | tostring].primary.model // ""' "${TIERS_FILE}" 2>/dev/null)
  [ -n "${_p}" ] && target_provider="${_p}"
  [ -n "${_m}" ] && target_model="${_m}"
fi

# ---- Log entry ----
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null)
desc_short=$(printf '%s' "${description}" | head -c 200 | tr '\n' ' ')

entry=$(jq -cn \
  --arg ts "${timestamp}" \
  --arg desc "${desc_short}" \
  --arg sub "${sub_type}" \
  --arg model "${model}" \
  --argjson tier "${best_tier}" \
  --arg provider "${target_provider}" \
  --arg tmodel "${target_model}" \
  --arg reason "${reason}" \
  '{
    timestamp: $ts,
    description: $desc,
    subagent_type: $sub,
    model_requested: $model,
    tier: $tier,
    target_provider: $provider,
    target_model: $tmodel,
    reason: $reason
  }' 2>/dev/null)

[ -n "${entry}" ] && printf '%s\n' "${entry}" >> "${LOG_FILE}" 2>/dev/null

# ---- Log rotation ----
MAX_LOG_LINES="${ROUTER_MAX_LOG_LINES:-2000}"
current_lines=$(wc -l < "${LOG_FILE}" 2>/dev/null) || current_lines=0
if [ "${current_lines}" -gt "${MAX_LOG_LINES}" ]; then
  keep=$(( MAX_LOG_LINES * 4 / 5 ))
  tmp="/tmp/router-log-rotate.$$.jsonl"
  tail -n "${keep}" "${LOG_FILE}" > "${tmp}" 2>/dev/null \
    && cp "${tmp}" "${LOG_FILE}" 2>/dev/null \
    && rm -f "${tmp}" 2>/dev/null
fi

# ---- Hook output ----
# Detect tool-use keywords: if prompt contains bash/file/search ops, don't block
TOOL_USE_PATTERN="${TOOL_USE_PATTERN:-bash|glob|grep|install|execute|curl|npm |pip |webfetch|websearch}"
has_tool_use=false
if printf '%s' "${haystack}" | grep -Eqi "${TOOL_USE_PATTERN}"; then
  has_tool_use=true
fi

advisory="ROUTER tier=${best_tier} provider=${target_provider} model=${target_model} — ${reason}"

# Never block when caller explicitly specified a Claude model alias — they've already decided
caller_explicit_model=false
case "${model}" in haiku|sonnet|opus) caller_explicit_model=true ;; esac

if [ "${ROUTER_BLOCK_ENABLED}" = "true" ] \
   && [ "${best_tier}" -lt 4 ] \
   && [ "${sub_type}" = "general-purpose" ] \
   && [ "${has_tool_use}" = "false" ] \
   && [ "${caller_explicit_model}" = "false" ]; then
  # Deny: redirect to cheaper tier
  jq -cn \
    --arg adv "${advisory}" \
    '{hookSpecificOutput: {permissionDecision: "deny", denyReason: ("Use cheaper tier instead. " + $adv), additionalContext: $adv}}' 2>/dev/null
else
  # Advisory only
  jq -cn --arg adv "${advisory}" \
    '{hookSpecificOutput: {additionalContext: $adv}}' 2>/dev/null
fi

exit 0
