#!/bin/bash
# Claude Code usage tracker - Stop event handler
# Reads transcript_path from Stop event, parses token usage, writes to usage-tracker.json

TRACKER_FILE="$HOME/.claude/usage-tracker.json"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Read Stop event JSON from stdin
HOOK_DATA=$(cat)

SESSION_ID=$(echo "$HOOK_DATA" | jq -r '.session_id // empty')
TRANSCRIPT_PATH=$(echo "$HOOK_DATA" | jq -r '.transcript_path // empty')

# Nothing to track if no session or transcript
if [ -z "$SESSION_ID" ] || [ -z "$TRANSCRIPT_PATH" ]; then
  exit 0
fi

# Convert Windows-style path (C:\...) to bash path (/c/...)
TRANSCRIPT_PATH=$(echo "$TRANSCRIPT_PATH" | sed 's|\\|/|g' | sed 's|^\([A-Za-z]\):|/\L\1|')

if [ ! -f "$TRANSCRIPT_PATH" ]; then
  exit 0
fi

# Parse transcript: sum token usage, deduplicate by requestId, infer model
USAGE_DATA=$(python3 - "$TRANSCRIPT_PATH" <<'PYEOF'
import json, sys

transcript_path = sys.argv[1]
totals = {
    "input_tokens": 0,
    "output_tokens": 0,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
}
model = "claude-sonnet-4-6"
seen_request_ids = set()

with open(transcript_path, encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        if entry.get("type") != "assistant":
            continue

        # Deduplicate: same requestId = same API call logged multiple times
        req_id = entry.get("requestId", "")
        if req_id:
            if req_id in seen_request_ids:
                continue
            seen_request_ids.add(req_id)

        msg = entry.get("message", {})
        if isinstance(msg, dict):
            if msg.get("model"):
                model = msg["model"]
            usage = msg.get("usage", {})
            for key in totals:
                totals[key] += usage.get(key, 0)

# Model pricing (USD per 1M tokens)
pricing = {
    "claude-sonnet-4-6":  {"input": 3.00,  "output": 15.00, "cache_write": 3.75,  "cache_read": 0.30},
    "claude-opus-4-6":    {"input": 15.00, "output": 75.00, "cache_write": 18.75, "cache_read": 1.50},
    "claude-haiku-4-5":   {"input": 0.80,  "output": 4.00,  "cache_write": 1.00,  "cache_read": 0.08},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00, "cache_write": 1.00, "cache_read": 0.08},
}
p = pricing.get(model, pricing["claude-sonnet-4-6"])

cost = (
    totals["input_tokens"]                  * p["input"]       / 1_000_000 +
    totals["output_tokens"]                 * p["output"]      / 1_000_000 +
    totals["cache_creation_input_tokens"]   * p["cache_write"] / 1_000_000 +
    totals["cache_read_input_tokens"]       * p["cache_read"]  / 1_000_000
)

print(json.dumps({
    "model": model,
    "input_tokens": totals["input_tokens"],
    "output_tokens": totals["output_tokens"],
    "cache_creation_input_tokens": totals["cache_creation_input_tokens"],
    "cache_read_input_tokens": totals["cache_read_input_tokens"],
    "total_tokens": sum(totals.values()),
    "cost_usd": round(cost, 6),
    "api_calls": len(seen_request_ids),
}))
PYEOF
)

if [ -z "$USAGE_DATA" ]; then
  exit 0
fi

MODEL=$(echo "$USAGE_DATA" | jq -r '.model')
COST=$(echo "$USAGE_DATA" | jq -r '.cost_usd')
INPUT=$(echo "$USAGE_DATA" | jq -r '.input_tokens')
OUTPUT=$(echo "$USAGE_DATA" | jq -r '.output_tokens')
CACHE_WRITE=$(echo "$USAGE_DATA" | jq -r '.cache_creation_input_tokens')
CACHE_READ=$(echo "$USAGE_DATA" | jq -r '.cache_read_input_tokens')
TOTAL=$(echo "$USAGE_DATA" | jq -r '.total_tokens')
API_CALLS=$(echo "$USAGE_DATA" | jq -r '.api_calls')

SESSION_ENTRY=$(cat <<ENTRY
{
  "timestamp": "$TIMESTAMP",
  "sessionId": "$SESSION_ID",
  "model": "$MODEL",
  "apiCalls": $API_CALLS,
  "tokens": {
    "input": $INPUT,
    "output": $OUTPUT,
    "cacheCreation": $CACHE_WRITE,
    "cacheRead": $CACHE_READ,
    "total": $TOTAL
  },
  "costUsd": $COST
}
ENTRY
)

# Initialise tracker file if missing
if [ ! -f "$TRACKER_FILE" ]; then
  echo '{"sessions":[]}' > "$TRACKER_FILE"
fi

# Log rotation: archive if > 10MB
LOG_SIZE=$(stat -c%s "$TRACKER_FILE" 2>/dev/null || stat -f%z "$TRACKER_FILE" 2>/dev/null || echo 0)
if [ "$LOG_SIZE" -gt 10485760 ]; then
  mv "$TRACKER_FILE" "${TRACKER_FILE%.json}-$(date +%Y%m%d).json"
  echo '{"sessions":[]}' > "$TRACKER_FILE"
fi

TEMP=$(mktemp)
jq ".sessions += [$SESSION_ENTRY]" "$TRACKER_FILE" > "$TEMP" && mv "$TEMP" "$TRACKER_FILE"

# ── AgentOps bridge ──────────────────────────────────────────────────────────
# Emit standardised AgentOps JSONL events (schema_version 1.0.0) via audit_log.py.
# Three event types: token_usage, cost_estimate, model_call.
# Events are ingestible by observability/ingest_jsonl.py → agentops.sqlite.
HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"

_emit_agentops_event() {
  local event_type="$1"
  local payload_json="$2"
  python3 - <<PYEOF
import sys, os
sys.path.insert(0, r"$HOOKS_DIR")
try:
    import argparse
    from audit_log import DEFAULT_LOG_PATH, append_event, build_event
    from pathlib import Path
    args = argparse.Namespace(
        event_type="$event_type",
        event_id=None, timestamp=None, severity="info",
        source_repo=os.getenv("AGENTOPS_SOURCE_REPO", "kas1987/claude-config"),
        source_component="hooks.usage_tracker",
        agent_id=os.getenv("AGENTOPS_AGENT_ID"),
        session_id="$SESSION_ID",
        task_id=os.getenv("AGENTOPS_TASK_ID"),
        run_id=os.getenv("AGENTOPS_RUN_ID"),
        parent_event_id=None, duration_ms=None,
    )
    import json
    payload = json.loads(r"""$payload_json""")
    log_path = Path(os.getenv("AGENTOPS_LOG_PATH", str(DEFAULT_LOG_PATH)))
    append_event(build_event(args, payload), log_path)
except Exception as exc:
    pass  # best-effort; never break the hook
PYEOF
}

_emit_agentops_event "token_usage" \
  "{\"model\":\"$MODEL\",\"provider\":\"$(echo "$MODEL" | grep -qi "ollama\|llama\|mistral\|gemma\|qwen" && echo ollama || echo anthropic)\",\"input_tokens\":$INPUT,\"output_tokens\":$OUTPUT,\"cache_write_tokens\":$CACHE_WRITE,\"cache_read_tokens\":$CACHE_READ,\"total_tokens\":$TOTAL,\"api_calls\":$API_CALLS}"

_emit_agentops_event "cost_estimate" \
  "{\"model\":\"$MODEL\",\"provider\":\"$(echo "$MODEL" | grep -qi "ollama\|llama\|mistral\|gemma\|qwen" && echo ollama || echo anthropic)\",\"estimated_cost_usd\":$COST}"

_emit_agentops_event "model_call" \
  "{\"model\":\"$MODEL\",\"provider\":\"$(echo "$MODEL" | grep -qi "ollama\|llama\|mistral\|gemma\|qwen" && echo ollama || echo anthropic)\",\"api_calls\":$API_CALLS,\"input_tokens\":$INPUT,\"output_tokens\":$OUTPUT,\"estimated_cost_usd\":$COST}"
# ── end AgentOps bridge ───────────────────────────────────────────────────────

exit 0
