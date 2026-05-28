#!/usr/bin/env bash
# Auto-commits packaged deliverable and pushes to current session branch.
# Blocked on master/main — always requires a session/* branch.
# Env: ISSUE_ID, ISSUE_TITLE, REVIEW_TIER, AUTO_MERGE (optional, default=0)

ISSUE_ID="${ISSUE_ID:-unknown}"
ISSUE_TITLE="${ISSUE_TITLE:-Deliverable}"
REVIEW_TIER="${REVIEW_TIER:-2}"
DELIVERABLE_DIR="$HOME/.claude/.agents/review/deliverables"

BRANCH=$(git branch --show-current 2>/dev/null)

# Hard block on master/main — harness constraint
if [[ "$BRANCH" == "master" || "$BRANCH" == "main" || -z "$BRANCH" ]]; then
  echo "[auto-push] BLOCKED: on master/main or no branch. Create session branch first." >&2
  exit 1
fi

# Stage only the deliverables directory (never git add -A — prevents secret staging)
git add "$DELIVERABLE_DIR/" 2>/dev/null

# Nothing staged? Nothing to commit.
if git diff --cached --quiet 2>/dev/null; then
  echo "[auto-push] Nothing to commit in deliverables dir — skipping push." >&2
  exit 0
fi

git commit -m "$(cat <<EOF
chore: auto-package review deliverable for $ISSUE_ID

Review tier: $REVIEW_TIER
Verdict: PASS
Multica issue: $ISSUE_ID

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)" 2>/dev/null || {
  echo "[auto-push] Commit failed" >&2
  exit 1
}

# Use --set-upstream on first push so subsequent pushes don't need -u
if git rev-parse --abbrev-ref "@{upstream}" &>/dev/null 2>&1; then
  git push origin "$BRANCH" 2>/dev/null
else
  git push --set-upstream origin "$BRANCH" 2>/dev/null
fi || {
  echo "[auto-push] Push failed" >&2
  exit 1
}

echo "[auto-push] Pushed to $BRANCH" >&2

if [ "${AUTO_MERGE:-0}" = "1" ]; then
  gh pr merge --squash --auto 2>/dev/null || true
else
  gh pr create --draft \
    --title "[$ISSUE_ID] $ISSUE_TITLE" \
    --body "Auto-packaged from Multica in-review pipeline. Review tier: $REVIEW_TIER." \
    2>/dev/null || echo "[auto-push] gh pr create skipped (may already exist)" >&2
fi

exit 0
