#!/usr/bin/env bash
# multi-provider-dispatch.sh — dispatch a prompt file to a provider tier.
#
# Usage:
#   multi-provider-dispatch.sh <tier> <prompt-file>   dispatch tier 0-4
#   multi-provider-dispatch.sh --auto <prompt-file>   read router log, pick tier
#   multi-provider-dispatch.sh --test                 smoke all tiers 0-3
#   multi-provider-dispatch.sh --help                 show Usage
#
# Outputs JSON to stdout. Writes log entry to dispatch.jsonl.
# Exit codes: 0=success or usage, 1=error/all-failed

set -u

TIERS_FILE="${ROUTER_TIERS_FILE:-${HOME}/.claude/config/provider-tiers.json}"
LOG_DIR="${ROUTER_LOG_DIR:-${HOME}/.claude/.agents/router}"
DISPATCH_LOG="${LOG_DIR}/dispatch.jsonl"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"

mkdir -p "${LOG_DIR}" 2>/dev/null || true

# ---- helpers ----

usage() {
  printf 'Usage:\n'
  printf '  multi-provider-dispatch.sh <tier> <prompt-file>\n'
  printf '  multi-provider-dispatch.sh --auto <prompt-file>\n'
  printf '  multi-provider-dispatch.sh --test\n'
  printf '  multi-provider-dispatch.sh --help\n'
}

error_json() {
  local tier="${1:-?}" provider="${2:-unknown}" model="${3:-unknown}" msg="${4:-dispatch failed}"
  jq -cn \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
    --argjson tier "${tier}" \
    --arg provider "${provider}" \
    --arg model "${model}" \
    --arg msg "${msg}" \
    '{error: $msg, tier: $tier, provider: $provider, model: $model, timestamp: $ts}'
}

log_dispatch() {
  local tier="${1}" provider="${2}" model="${3}" path="${4}" status="${5:-attempted}"
  jq -cn \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
    --argjson tier "${tier}" \
    --arg provider "${provider}" \
    --arg model "${model}" \
    --arg path "${path}" \
    --arg status "${status}" \
    '{timestamp: $ts, tier: $tier, provider: $provider, model: $model, path: $path, status: $status}' \
    >> "${DISPATCH_LOG}" 2>/dev/null || true
}

resolve_tier() {
  local tier="$1" slot="${2:-primary}"
  local provider="unknown" model="unknown"
  if [ -r "${TIERS_FILE}" ]; then
    provider=$(jq -r --argjson t "${tier}" --arg s "${slot}" '.tiers[$t | tostring][$s].provider // "unknown"' "${TIERS_FILE}" 2>/dev/null)
    model=$(jq -r --argjson t "${tier}" --arg s "${slot}" '.tiers[$t | tostring][$s].model // "unknown"' "${TIERS_FILE}" 2>/dev/null)
  fi
  printf '%s %s' "${provider}" "${model}"
}

# dispatch_provider: send prompt_file to a specific provider+model.
# Writes body to a tempfile to avoid shell-expansion corruption of unicode/special chars.
# Returns 0 + JSON on success, 1 + error JSON on failure.
dispatch_provider() {
  local provider="$1" model="$2" prompt_file="$3" tier="${4:-?}"
  local tmpbody
  tmpbody=$(mktemp /tmp/dispatch-body-XXXXXX.json)

  case "${provider}" in
    ollama)
      jq -cn --arg m "${model}" --rawfile p "${prompt_file}" \
        '{model:$m,prompt:$p,stream:false}' > "${tmpbody}" 2>/dev/null
      local response
      response=$(curl --silent --fail --max-time 10 \
        -X POST "${OLLAMA_URL}/api/generate" \
        -H 'Content-Type: application/json' \
        -d "@${tmpbody}" 2>/dev/null)
      local rc=$?
      rm -f "${tmpbody}"
      [ $rc -ne 0 ] && { error_json "${tier}" "${provider}" "${model}" "ollama unreachable at ${OLLAMA_URL}"; return 1; }
      printf '%s' "${response}"; return 0
      ;;
    featherless)
      local key="${FEATHERLESS_API_KEY:-}"
      [ -z "${key}" ] && [ -n "${FEATHERLESS_API_KEY_PATH:-}" ] && [ -f "${FEATHERLESS_API_KEY_PATH}" ] && \
        key=$(tr -d '[:space:]' < "${FEATHERLESS_API_KEY_PATH}")
      if [ -z "${key}" ]; then
        rm -f "${tmpbody}"
        error_json "${tier}" "${provider}" "${model}" "FEATHERLESS_API_KEY not set"
        return 1
      fi
      jq -cn --arg m "${model}" --rawfile p "${prompt_file}" \
        '{model:$m,messages:[{role:"user",content:$p}],max_tokens:512}' > "${tmpbody}" 2>/dev/null
      local response
      response=$(curl --silent --fail --max-time 20 \
        -X POST "${FEATHERLESS_BASE_URL:-https://api.featherless.ai/v1}/chat/completions" \
        -H "Authorization: Bearer ${key}" \
        -H "Content-Type: application/json" \
        -d "@${tmpbody}" 2>/dev/null)
      local rc=$?
      rm -f "${tmpbody}"
      [ $rc -ne 0 ] && { error_json "${tier}" "${provider}" "${model}" "featherless API call failed"; return 1; }
      # Check for capacity/error in response body
      local err
      err=$(printf '%s' "${response}" | jq -r '.error.message // empty' 2>/dev/null)
      [ -n "${err}" ] && { error_json "${tier}" "${provider}" "${model}" "${err}"; return 1; }
      printf '%s' "${response}"; return 0
      ;;
    openai)
      local key="${OPENAI_API_KEY:-}"
      [ -z "${key}" ] && [ -n "${OPENAI_API_KEY_PATH:-}" ] && [ -f "${OPENAI_API_KEY_PATH}" ] && \
        key=$(tr -d '[:space:]' < "${OPENAI_API_KEY_PATH}")
      if [ -z "${key}" ]; then
        rm -f "${tmpbody}"
        error_json "${tier}" "${provider}" "${model}" "OPENAI_API_KEY not set"
        return 1
      fi
      jq -cn --arg m "${model}" --rawfile p "${prompt_file}" \
        '{model:$m,messages:[{role:"user",content:$p}],max_tokens:512}' > "${tmpbody}" 2>/dev/null
      local response
      response=$(curl --silent --fail --max-time 20 \
        -X POST "https://api.openai.com/v1/chat/completions" \
        -H "Authorization: Bearer ${key}" \
        -H "Content-Type: application/json" \
        -d "@${tmpbody}" 2>/dev/null)
      local rc=$?
      rm -f "${tmpbody}"
      [ $rc -ne 0 ] && { error_json "${tier}" "${provider}" "${model}" "openai API call failed"; return 1; }
      printf '%s' "${response}"; return 0
      ;;
    gemini)
      local key="${GEMINI_API_KEY:-}"
      [ -z "${key}" ] && [ -n "${GEMINI_API_KEY_PATH:-}" ] && [ -f "${GEMINI_API_KEY_PATH}" ] && \
        key=$(tr -d '[:space:]' < "${GEMINI_API_KEY_PATH}")
      if [ -z "${key}" ]; then
        rm -f "${tmpbody}"
        error_json "${tier}" "${provider}" "${model}" "GEMINI_API_KEY not set"
        return 1
      fi
      jq -cn --rawfile p "${prompt_file}" \
        '{contents:[{parts:[{text:$p}]}]}' > "${tmpbody}" 2>/dev/null
      local response
      response=$(curl --silent --fail --max-time 20 \
        "https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}" \
        -H "Content-Type: application/json" \
        -d "@${tmpbody}" 2>/dev/null)
      local rc=$?
      rm -f "${tmpbody}"
      [ $rc -ne 0 ] && { error_json "${tier}" "${provider}" "${model}" "gemini API call failed"; return 1; }
      printf '%s' "${response}"; return 0
      ;;
    *)
      rm -f "${tmpbody}"
      error_json "${tier}" "${provider}" "${model}" "unknown provider: ${provider}"
      return 1
      ;;
  esac
}

dispatch_tier() {
  local tier="$1" prompt_file="$2"

  # Tier 4 = Claude native, no external dispatch
  [ "${tier}" = "4" ] && {
    local pair; pair=$(resolve_tier "${tier}")
    local provider model
    provider=$(printf '%s' "${pair}" | cut -d' ' -f1)
    model=$(printf '%s' "${pair}" | cut -d' ' -f2-)
    jq -cn --argjson t "${tier}" --arg provider "${provider}" --arg model "${model}" \
      '{note:"tier-4 (claude) is handled natively by Claude Code; no external dispatch",tier:$t,provider:$provider,model:$model}'
    return 0
  }

  local primary_pair fallback_pair
  primary_pair=$(resolve_tier "${tier}" primary)
  fallback_pair=$(resolve_tier "${tier}" fallback)
  local p_provider p_model f_provider f_model
  p_provider=$(printf '%s' "${primary_pair}" | cut -d' ' -f1)
  p_model=$(printf '%s' "${primary_pair}" | cut -d' ' -f2-)
  f_provider=$(printf '%s' "${fallback_pair}" | cut -d' ' -f1)
  f_model=$(printf '%s' "${fallback_pair}" | cut -d' ' -f2-)

  log_dispatch "${tier}" "${p_provider}" "${p_model}" "${prompt_file}" "attempted"

  # Try primary
  local result
  if result=$(dispatch_provider "${p_provider}" "${p_model}" "${prompt_file}" "${tier}" 2>/dev/null); then
    log_dispatch "${tier}" "${p_provider}" "${p_model}" "${prompt_file}" "success"
    printf '%s' "${result}"
    return 0
  fi

  # Try fallback if configured
  if [ "${f_provider}" != "unknown" ] && [ "${f_provider}" != "${p_provider}" -o "${f_model}" != "${p_model}" ]; then
    log_dispatch "${tier}" "${f_provider}" "${f_model}" "${prompt_file}" "fallback-attempted"
    if result=$(dispatch_provider "${f_provider}" "${f_model}" "${prompt_file}" "${tier}" 2>/dev/null); then
      log_dispatch "${tier}" "${f_provider}" "${f_model}" "${prompt_file}" "fallback-success"
      printf '%s' "${result}"
      return 0
    fi
  fi

  error_json "${tier}" "${p_provider}" "${p_model}" "all providers failed for tier ${tier}"
  return 1
}

# ---- main ----

case "${1:-}" in
  ""|--help)
    usage
    exit 0
    ;;
  --auto)
    if [ -z "${2:-}" ]; then
      printf 'usage: --auto requires a prompt file argument\n' >&2
      exit 1
    fi
    prompt_file="$2"
    if [ ! -f "${prompt_file}" ]; then
      error_json "0" "unknown" "unknown" "prompt file not found: ${prompt_file}"
      exit 1
    fi
    # Read latest recommended tier from router log
    tier=4
    if [ -f "${LOG_DIR}/log.jsonl" ]; then
      _t=$(tail -1 "${LOG_DIR}/log.jsonl" | jq -r '.tier // 4' 2>/dev/null)
      [[ "${_t}" =~ ^[0-4]$ ]] && tier="${_t}"
    fi
    dispatch_tier "${tier}" "${prompt_file}"
    ;;
  --test)
    printf 'Smoke testing tiers 0-3 (expect errors without API keys/Ollama):\n'
    prompt_file=$(mktemp)
    printf 'Reply with exactly: test OK' > "${prompt_file}"
    for t in 0 1 2 3; do
      pair=$(resolve_tier "${t}")
      provider=$(printf '%s' "${pair}" | cut -d' ' -f1)
      printf 'tier %d (%s): ' "${t}" "${provider}"
      result=$(dispatch_tier "${t}" "${prompt_file}" 2>/dev/null)
      if printf '%s' "${result}" | jq -e '.error' >/dev/null 2>&1; then
        msg=$(printf '%s' "${result}" | jq -r '.error' 2>/dev/null)
        printf 'error: %s\n' "${msg}"
      elif printf '%s' "${result}" | jq -e '.note' >/dev/null 2>&1; then
        printf 'note: native\n'
      else
        printf 'ok\n'
      fi
    done
    rm -f "${prompt_file}"
    exit 0
    ;;
  [0-9]*)
    tier="$1"
    prompt_file="${2:-}"
    if [ -z "${prompt_file}" ] || [ ! -f "${prompt_file}" ]; then
      error_json "${tier}" "unknown" "unknown" "prompt file not found: ${prompt_file:-<missing>}"
      exit 1
    fi
    dispatch_tier "${tier}" "${prompt_file}"
    ;;
  *)
    usage
    exit 0
    ;;
esac
