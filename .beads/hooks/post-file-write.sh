#!/bin/bash
# Post-file-write formatting hook - Claude Code PostToolUse handler
# Receives PostToolUse event JSON on stdin for Write, Edit, NotebookEdit tools.
# Runs ruff format on .py files; validates .json files.

# Read PostToolUse event JSON from stdin
HOOK_DATA=$(cat)

# Extract file path.
# Write/Edit use tool_input.file_path; NotebookEdit uses tool_input.notebook_path.
FILE=$(echo "$HOOK_DATA" | jq -r '
  .tool_input.file_path //
  .tool_input.notebook_path //
  empty
' 2>/dev/null)

if [ -z "$FILE" ]; then
  exit 0
fi

# Convert Windows-style path (C:\...) to bash path (/c/...)
FILE=$(echo "$FILE" | sed 's|\\|/|g' | sed 's|^\([A-Za-z]\):|/\L\1|')

if [ ! -f "$FILE" ]; then
  exit 0
fi

# Python: format with ruff
if [[ "$FILE" == *.py ]]; then
  if command -v ruff &>/dev/null; then
    ruff format "$FILE" 2>/dev/null || true
  fi
fi

# JSON: validate (warn only, never block)
if [[ "$FILE" == *.json ]]; then
  python3 -m json.tool "$FILE" > /dev/null 2>&1 \
    || echo "WARN: invalid JSON in $FILE"
fi

exit 0
