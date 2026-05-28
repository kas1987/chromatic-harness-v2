#!/usr/bin/env bash
# ollama-liveness.sh — SessionStart hook that probes Ollama at localhost:11434.
# Writes ~/.claude/.agents/router/ollama-status.json so model-router.sh can
# skip tier 0 instantly instead of timing out on every Agent call.
# Non-blocking: always exits 0.

set -u

STATUS_DIR="${HOME}/.claude/.agents/router"
STATUS_FILE="${STATUS_DIR}/ollama-status.json"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
TIMEOUT=1   # seconds — fast probe, don't slow session start

mkdir -p "${STATUS_DIR}" 2>/dev/null

ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Probe /api/tags — lightweight, returns model list
start_ms=$(date +%s%3N 2>/dev/null || echo 0)
response=$(curl --silent --fail --max-time "${TIMEOUT}" \
  "${OLLAMA_URL}/api/tags" 2>/dev/null) && probe_ok=true || probe_ok=false
end_ms=$(date +%s%3N 2>/dev/null || echo 0)
elapsed=$(( end_ms - start_ms ))

if ${probe_ok}; then
  model_count=$(printf '%s' "${response}" | jq '.models | length' 2>/dev/null || echo 0)
  jq -cn \
    --arg ts "${ts}" \
    --arg url "${OLLAMA_URL}" \
    --argjson ms "${elapsed}" \
    --argjson n "${model_count}" \
    '{up:true,checked_at:$ts,ollama_url:$url,response_ms:$ms,model_count:$n}' \
    > "${STATUS_FILE}" 2>/dev/null
else
  jq -cn \
    --arg ts "${ts}" \
    --arg url "${OLLAMA_URL}" \
    --argjson ms "${elapsed}" \
    '{up:false,checked_at:$ts,ollama_url:$url,response_ms:$ms,model_count:0}' \
    > "${STATUS_FILE}" 2>/dev/null
  # Surface as systemMessage so Claude knows tier-0 routing is disabled
  printf '{"systemMessage": "ROUTER: Ollama unreachable at %s — tier-0 (local) routing disabled. Tier-1+ active. Start Ollama to restore local dispatch."}\n' \
    "${OLLAMA_URL}"
fi

exit 0
