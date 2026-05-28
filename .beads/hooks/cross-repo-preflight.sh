#!/usr/bin/env bash
# Cross-repo preflight - PreToolUse hook for Write/Edit.
#
# Reads PreToolUse event JSON on stdin. Inspects the proposed write target.
# If the target file lives OUTSIDE the current session's primary working
# directory ($CLAUDE_PROJECT_DIR or pwd at session start), runs
# 01_HARNESS/cross_repo_preflight.py to scan for in-flight workstreams in
# the target repo.
#
# Doctrine: 05_DOCS/workstream-collision-doctrine.md (in prism-autonomy-harness)
#
# Exit codes (per Claude Code hook contract):
#   0 - allow tool call (CLEAR or WARN; warnings printed to stderr for visibility)
#   2 - block tool call (collision detected)
#
# Disabled by default until enabled in ~/.claude/settings.json. See doctrine
# §Enablement for the settings.json snippet.

set -uo pipefail

# Bypass switch for emergency / debugging.
if [[ "${CLAUDE_PREFLIGHT_BYPASS:-0}" == "1" ]]; then
  exit 0
fi

# Read PreToolUse event from stdin.
HOOK_DATA=$(cat)
if [[ -z "$HOOK_DATA" ]]; then
  exit 0
fi

# Only act on Write and Edit. NotebookEdit and others pass through.
TOOL=$(printf '%s' "$HOOK_DATA" | jq -r '.tool_name // empty' 2>/dev/null)
case "$TOOL" in
  Write|Edit) ;;
  *) exit 0 ;;
esac

FILE=$(printf '%s' "$HOOK_DATA" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
if [[ -z "$FILE" ]]; then
  exit 0
fi

# Normalize Windows path (C:\foo) to bash path (/c/foo).
NORM=$(printf '%s' "$FILE" | sed 's|\\|/|g' | sed 's|^\([A-Za-z]\):|/\L\1|')

# Determine primary working dir for this session.
SESSION_CWD="${CLAUDE_PROJECT_DIR:-$(pwd)}"
SESSION_CWD_NORM=$(printf '%s' "$SESSION_CWD" | sed 's|\\|/|g' | sed 's|^\([A-Za-z]\):|/\L\1|')

# If the target is inside the session cwd, no cross-repo concern — exit clean.
case "$NORM" in
  "$SESSION_CWD_NORM"|"$SESSION_CWD_NORM"/*) exit 0 ;;
esac

# Find the git repo root the target belongs to.
TARGET_DIR=$(dirname "$NORM")
if [[ ! -d "$TARGET_DIR" ]]; then
  # Path may not exist yet (new file); walk up until we find one.
  while [[ "$TARGET_DIR" != "/" && ! -d "$TARGET_DIR" ]]; do
    TARGET_DIR=$(dirname "$TARGET_DIR")
  done
fi

if [[ "$TARGET_DIR" == "/" ]]; then
  exit 0
fi

TARGET_REPO=$(git -C "$TARGET_DIR" rev-parse --show-toplevel 2>/dev/null)
if [[ -z "$TARGET_REPO" ]]; then
  # Not a git repo — nothing to scan.
  exit 0
fi

# Same-repo check (handles symlinks/case).
# IMPORTANT: Normalize TARGET_REPO through the SAME sed pipeline used for NORM
# so the prefix-strip below works on Windows/msys where `cd && pwd` can return
# a divergent mount form (e.g. /tmp/...) for paths that NORM rendered as
# /c/Users/.../Temp/... — without this, REL_PATH silently falls back to
# basename and collision protection is bypassed.
TARGET_REPO_NORM=$(printf '%s' "$TARGET_REPO" | sed 's|\\|/|g' | sed 's|^\([A-Za-z]\):|/\L\1|')
if [[ "$TARGET_REPO_NORM" == "$SESSION_CWD_NORM" ]]; then
  exit 0
fi

# Compute target-path relative to repo root.
REL_PATH="${NORM#$TARGET_REPO_NORM/}"
if [[ "$REL_PATH" == "$NORM" ]]; then
  # stripping failed; fall back to bare filename to still get *some* probe coverage.
  REL_PATH=$(basename "$NORM")
fi

# Locate the preflight scanner. CLAUDE_PREFLIGHT_SCANNER_PATH overrides all candidates
# (empty string forces scanner-absent path, useful for testing).
PREFLIGHT=""
if [[ -v CLAUDE_PREFLIGHT_SCANNER_PATH ]]; then
  # Explicit override: use it directly (allows test injection and forced-miss via empty string)
  PREFLIGHT="${CLAUDE_PREFLIGHT_SCANNER_PATH}"
else
  for candidate in \
    "$SESSION_CWD/01_HARNESS/cross_repo_preflight.py" \
    "$HOME/.claude/scripts/cross_repo_preflight.py" \
    "/c/Repos/Poly-Chromatic/prism-autonomy-harness/01_HARNESS/cross_repo_preflight.py"; do
    if [[ -f "$candidate" ]]; then
      PREFLIGHT="$candidate"
      break
    fi
  done
fi

if [[ -z "$PREFLIGHT" ]]; then
  if [[ "${CLAUDE_PREFLIGHT_STRICT:-0}" == "1" ]]; then
    printf '%s\n' '{"systemMessage":"[cross-repo-preflight] BLOCKED: cross-repo write attempted but scanner (cross_repo_preflight.py) not found. Set CLAUDE_PREFLIGHT_BYPASS=1 to override, or install the scanner at ~/.claude/scripts/cross_repo_preflight.py."}'
    echo "cross-repo preflight: scanner not found and CLAUDE_PREFLIGHT_STRICT=1 — blocking." >&2
    exit 2
  fi
  printf '%s\n' '{"systemMessage":"[cross-repo-preflight] WARN: cross-repo write allowed but scanner not found — collision protection inactive. Install scanner or set CLAUDE_PREFLIGHT_STRICT=1 to block."}'
  exit 0
fi

# Run the scan. Capture JSON output and exit code.
SESSION_ID="${CLAUDE_SESSION_ID:-${USER:-unknown}-$$}"
SCAN_ARGS=(scan \
  --repo "$TARGET_REPO_NORM" \
  --target-path "$REL_PATH" \
  --session "$SESSION_ID")
if [[ -n "${CLAUDE_PREFLIGHT_REPO_ID:-}" ]]; then
  SCAN_ARGS+=(--repo-id "$CLAUDE_PREFLIGHT_REPO_ID")
fi
SCAN_OUT=$(python3 "$PREFLIGHT" "${SCAN_ARGS[@]}" 2>&1)
SCAN_RC=$?

VERDICT=$(printf '%s' "$SCAN_OUT" | python3 -c \
  "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('verdict','ERROR'))" \
  2>/dev/null || echo "ERROR")

case "$VERDICT" in
  CLEAR)
    exit 0
    ;;
  WARN)
    {
      echo "==== cross-repo preflight WARN ===="
      echo "Tool: $TOOL  File: $FILE"
      echo "Target repo: $TARGET_REPO_NORM"
      echo "Target path: $REL_PATH"
      printf '%s\n' "$SCAN_OUT"
      echo "===================================="
    } >&2
    exit 0
    ;;
  BLOCK)
    # Auto-emit an align_request to the owning workstream. Best-effort: never
    # let emission failure mask the BLOCK itself. The block always stands.
    EMIT_OUT=""
    EMIT_RC=0
    ALIGN_SCRIPT=""
    for cand in \
      "$SESSION_CWD/01_HARNESS/align_request.py" \
      "$HOME/.claude/scripts/align_request.py" \
      "/c/Repos/Poly-Chromatic/prism-autonomy-harness/01_HARNESS/align_request.py"; do
      if [[ -f "$cand" ]]; then
        ALIGN_SCRIPT="$cand"
        break
      fi
    done
    if [[ -n "$ALIGN_SCRIPT" ]] && [[ "${CLAUDE_PREFLIGHT_NO_EMIT:-0}" != "1" ]]; then
      EMIT_OUT=$(printf '%s' "$SCAN_OUT" | python3 "$ALIGN_SCRIPT" from-verdict - \
        --to-repo "$TARGET_REPO_NORM" \
        --from-epic "${CLAUDE_RPI_EPIC:-unknown}" \
        --from-repo "${CLAUDE_PROJECT_DIR##*/}" \
        --from-repo-path "${SESSION_CWD_NORM:-$PWD}" 2>&1) || EMIT_RC=$?
    fi
    {
      echo "==== cross-repo preflight BLOCK ===="
      echo "Tool: $TOOL  File: $FILE"
      echo "Target repo: $TARGET_REPO_NORM"
      echo "Target path: $REL_PATH"
      printf '%s\n' "$SCAN_OUT"
      echo ""
      if [[ -n "$EMIT_OUT" ]]; then
        echo "---- align_request emission ----"
        printf '%s\n' "$EMIT_OUT"
        echo "--------------------------------"
      fi
      echo "An active workstream owns this path. Align with the owning epic, or"
      echo "set CLAUDE_PREFLIGHT_BYPASS=1 to override (use sparingly, e.g. doctrine"
      echo "edits or your own session). Set CLAUDE_PREFLIGHT_NO_EMIT=1 to suppress"
      echo "auto-handoff to the owning workstream."
      echo "===================================="
    } >&2
    exit 2
    ;;
  *)
    # ERROR or unknown verdict — scanner ran but returned unexpected output.
    # Always fail-open: scanner execution errors are not the same as scanner finding a collision.
    # CLAUDE_PREFLIGHT_STRICT only gates the scanner-missing path, not scanner execution errors.
    echo "cross-repo preflight: scanner returned $VERDICT (rc=$SCAN_RC) — allowing (scanner execution error)" >&2
    printf '%s\n' "$SCAN_OUT" >&2
    exit 0
    ;;
esac
