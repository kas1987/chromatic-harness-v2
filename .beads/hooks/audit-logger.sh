#!/bin/bash
# Audit logging for tool execution

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOG_FILE="$HOME/.claude/audit.log"

# Log rotation: archive and start fresh if > 10MB
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(stat -c%s "$LOG_FILE" 2>/dev/null || stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$LOG_SIZE" -gt 10485760 ]; then
        mv "$LOG_FILE" "${LOG_FILE}.$(date '+%Y%m%d').bak"
    fi
fi

# Log tool execution
echo "[$TIMESTAMP] Tool executed: $*" >> "$LOG_FILE"

exit 0
