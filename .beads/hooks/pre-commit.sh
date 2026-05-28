#!/bin/bash
# Pre-commit validation hook - Claude Code PreToolUse/Bash handler
# Fast-exits for any non-commit bash command; only runs checks on git commits.
#
# Exit codes:
#   0  - allow the bash command to proceed
#   2  - block the bash command (secrets detected)

# Read PreToolUse event JSON from stdin
HOOK_DATA=$(cat)

# Fast-exit if this is not a git commit command
COMMAND=$(echo "$HOOK_DATA" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Honor escape hatch: AUTO_MODE_ENFORCED=1 git commit bypasses pre-commit checks
if echo "$COMMAND" | grep -qE '(^|\s)AUTO_MODE_ENFORCED=1\s'; then
  echo "[pre-commit] AUTO_MODE_ENFORCED=1 detected — bypassing checks (governance escape hatch)" >&2
  exit 0
fi

if ! echo "$COMMAND" | grep -qE '\bgit\s+commit\b'; then
  exit 0
fi

# Honor persistent auto-mode marker written by: pnpm run governance:auto-mode:enable
# Checks the repo being committed to (not ~/.claude), so works for all Prism repos
_REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [ -n "${_REPO_ROOT}" ] && [ -f "${_REPO_ROOT}/.security/AGENT_AUTO_MODE" ]; then
  echo "[pre-commit] AGENT_AUTO_MODE marker found — bypassing checks (persistent auto-mode)" >&2
  exit 0
fi

echo "=== Pre-commit checks ==="

# Staged Python files (used by checks 1 and 2)
STAGED_PY=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null | grep '\.py$' || true)

# [1/3] Python syntax on staged files
if [ -n "$STAGED_PY" ]; then
  echo "[1/3] Python syntax..."
  SYNTAX_OK=true
  while IFS= read -r f; do
    if ! python3 -m py_compile "$f" 2>/dev/null; then
      echo "  WARN: syntax error in $f"
      SYNTAX_OK=false
    fi
  done <<< "$STAGED_PY"
  $SYNTAX_OK && echo "  OK"
fi

# [2/3] Ruff linter on staged Python files only
if [ -n "$STAGED_PY" ] && command -v ruff &>/dev/null; then
  echo "[2/3] Ruff lint..."
  echo "$STAGED_PY" | xargs ruff check --select E,W,F --ignore E501 2>/dev/null || true
fi

# [3/3] Secrets scan — looks for assignment of credential-like values in staged diff.
# Requires: known secret key name + separator + quoted value >= 8 chars, or PEM header.
echo "[3/3] Secrets scan..."
STAGED_DIFF=$(git diff --cached 2>/dev/null)

# Build pattern in a variable to keep quoting sane
SECRET_PATTERN='(password|passwd|api_key|api_secret|secret_key|access_token|auth_token|aws_secret_access_key|private_key|github_personal_access_token)[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"']{8,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|ghp_[A-Za-z0-9_]{36,}'

if echo "$STAGED_DIFF" | grep -qiE "$SECRET_PATTERN"; then
  echo "  ERROR: potential secrets in staged changes!"
  echo "  Review: git diff --cached | grep -iE 'key|secret|token|password'"
  exit 2
fi
echo "  OK"

echo "=== All checks passed ==="
exit 0
