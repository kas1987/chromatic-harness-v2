#!/bin/bash
# Warn when a tool response exceeds ~5k tokens (~20k chars)
INPUT=$(cat)

RESPONSE_LEN=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(len(json.dumps(data.get('tool_response', ''))))
except:
    print(0)
" 2>/dev/null || echo "0")

THRESHOLD=20000

if [ "$RESPONSE_LEN" -gt "$THRESHOLD" ]; then
    TOKENS_EST=$((RESPONSE_LEN / 4))
    TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name','unknown'))" 2>/dev/null || echo "unknown")
    printf '{"systemMessage":"⚠️  %s returned ~%dk tokens (over 5k limit). Use targeted params to reduce size.","hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"RESPONSE SIZE EXCEEDED: %s returned ~%d tokens. Reduce with depth/target (browser_snapshot), limit (queries), or head_limit (Grep/Bash)."}}\n' \
        "$TOOL_NAME" "$((TOKENS_EST / 1000))" "$TOOL_NAME" "$TOKENS_EST"
fi
