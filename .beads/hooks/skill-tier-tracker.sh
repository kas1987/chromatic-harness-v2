#!/usr/bin/env bash
# skill-tier-tracker.sh v1 — PreToolUse hook for Skill tool calls (mc-6a5.2)
#
# When a skill is invoked, reads model_tier from the skill's SKILL.md frontmatter
# and writes it to .agents/router/active-skill.json with a timestamp.
# model-router.sh reads this file as a tier floor for subsequent Agent calls.
#
# Tier name → number mapping:
#   nano=0  micro=1  small=2  medium=3  large=4
#
# Exit codes: 0 always (fail-open)

set -u

LOG_DIR="${ROUTER_LOG_DIR:-${HOME}/.claude/.agents/router}"
SKILLS_DIR="${HOME}/.claude/skills"
ACTIVE_SKILL_FILE="${LOG_DIR}/active-skill.json"
TIER_TTL_SECONDS=180   # active-skill signal expires after 3 minutes of inactivity

mkdir -p "${LOG_DIR}" 2>/dev/null || exit 0

# ---- Read stdin ----
input=$(cat 2>/dev/null) || exit 0
[ -z "${input}" ] && exit 0

# Only act on Skill tool calls
tool_name=$(printf '%s' "${input}" | jq -r '.tool_name // ""' 2>/dev/null) || exit 0
[ "${tool_name}" != "Skill" ] && exit 0

skill_name=$(printf '%s' "${input}" | jq -r '.tool_input.skill // ""' 2>/dev/null)
[ -z "${skill_name}" ] && exit 0

# ---- Read model_tier from skill frontmatter ----
SKILL_FILE="${SKILLS_DIR}/${skill_name}/SKILL.md"
model_tier=""

if [ -f "${SKILL_FILE}" ]; then
  # Extract model_tier from frontmatter (between first two --- lines)
  # Handles both: "  model_tier: large" and "model_tier: large"
  model_tier=$(awk '
    /^---/ { if (in_fm) exit; in_fm=1; next }
    in_fm && /model_tier:/ { match($0, /model_tier:[[:space:]]*([a-z]+)/, a); print a[1]; exit }
  ' "${SKILL_FILE}" 2>/dev/null)
fi

# ---- Map tier name to number ----
tier_num=4   # default: large (fail-open to highest tier)
case "${model_tier}" in
  nano)   tier_num=0 ;;
  micro)  tier_num=1 ;;
  small)  tier_num=2 ;;
  medium) tier_num=3 ;;
  large)  tier_num=4 ;;
  "")     tier_num=4 ;;  # no declaration → assume large (orchestrator-safe)
esac

# ---- Write active-skill signal ----
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null)
ts_epoch=$(date +%s 2>/dev/null)

jq -cn \
  --arg skill "${skill_name}" \
  --arg model_tier "${model_tier:-unset}" \
  --argjson tier_num "${tier_num}" \
  --arg timestamp "${timestamp}" \
  --argjson ts_epoch "${ts_epoch}" \
  --argjson ttl "${TIER_TTL_SECONDS}" \
  '{
    skill: $skill,
    model_tier: $model_tier,
    tier_num: $tier_num,
    timestamp: $timestamp,
    ts_epoch: $ts_epoch,
    expires_at_epoch: ($ts_epoch + $ttl)
  }' > "${ACTIVE_SKILL_FILE}" 2>/dev/null

# ---- Advisory output (no blocking) ----
jq -cn \
  --arg skill "${skill_name}" \
  --arg tier "${model_tier:-unset}" \
  --argjson num "${tier_num}" \
  '{hookSpecificOutput: {additionalContext: ("SKILL-TIER: \($skill) declared model_tier=\($tier) (tier-\($num)) — floor active for next Agent calls")}}' \
  2>/dev/null

exit 0
