#!/usr/bin/env bash
# audit.sh — Claude Code hook configuration audit
# Usage: bash audit.sh [--phase=inventory|coverage|cost|verify]
# Output: Markdown report to stdout
# Requires: bash 4+ (macOS ships bash 3.2 — use homebrew bash or bash 4 explicitly)
#
# Reads: ~/.claude/settings.json, .claude/settings.json, .claude/settings.local.json

set -euo pipefail

PHASE="all"
for arg in "$@"; do
  case "$arg" in
    --phase=*) PHASE="${arg#--phase=}" ;;
  esac
done

DATE=$(date '+%Y-%m-%d %H:%M')
USER_SETTINGS="$HOME/.claude/settings.json"
PROJECT_SETTINGS=".claude/settings.json"
LOCAL_SETTINGS=".claude/settings.local.json"

# ── helpers ──────────────────────────────────────────────────────────────────

has_jq() { command -v jq >/dev/null 2>&1; }
has_python() { command -v python >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1; }
py() { command -v python3 >/dev/null 2>&1 && python3 "$@" || python "$@"; }

extract_hooks() {
  local file="$1" label="$2"
  if [ ! -f "$file" ]; then return; fi
  if ! has_jq; then
    echo "<!-- jq not found; cannot parse $file -->"
    return
  fi
  jq -r --arg src "$label" '
    .hooks // {} |
    to_entries[] |
    .key as $event |
    .value[] |
    .matcher as $matcher |
    .hooks[] |
    [$src, $event, ($matcher // "(none)"), .type, (.command // .prompt // "(agent)"), (.timeout // "unset")] |
    @tsv
  ' "$file" 2>/dev/null | tr -d '\r' || echo "<!-- parse error in $file -->"
}

# ── phase 1: inventory ────────────────────────────────────────────────────────

phase_inventory() {
  echo "## Phase 1: Inventory"
  echo ""
  echo "Settings files checked:"
  for f in "$USER_SETTINGS" "$PROJECT_SETTINGS" "$LOCAL_SETTINGS"; do
    if [ -f "$f" ]; then
      echo "- ✅ \`$f\`"
    else
      echo "- ❌ \`$f\` (not found)"
    fi
  done
  echo ""

  if ! has_jq; then
    echo "> ⚠️  \`jq\` not found — install jq for full inventory parsing."
    echo ""
    return
  fi

  echo "| Source | Event | Matcher | Type | Command | Timeout |"
  echo "|--------|-------|---------|------|---------|---------|"

  for entry in \
    "$USER_SETTINGS:~/.claude/settings.json" \
    "$PROJECT_SETTINGS:.claude/settings.json" \
    "$LOCAL_SETTINGS:.claude/settings.local.json"; do
    file="${entry%%:*}"
    label="${entry##*:}"
    extract_hooks "$file" "$label" | while IFS=$'\t' read -r src event matcher hook_type cmd timeout; do
      short_cmd="${cmd:0:60}"
      [ "${#cmd}" -gt 60 ] && short_cmd="${short_cmd}…"
      echo "| \`$src\` | \`$event\` | \`$matcher\` | $hook_type | \`$short_cmd\` | ${timeout}s |"
    done
  done
  echo ""
}

# ── phase 2: coverage ─────────────────────────────────────────────────────────

KNOWN_EVENTS=(
  SessionStart SessionEnd
  PreToolUse PostToolUse PostToolUseFailure
  UserPromptSubmit
  Stop
  PreCompact PostCompact
  Notification
)

HIGH_VALUE_EVENTS=(
  "PreToolUse:Bash guard (safety):HIGH"
  "PostToolUse:(none):response size guard:MED"
  "Stop:session cleanup / context guard:HIGH"
  "UserPromptSubmit:context pressure check:MED"
  "PreCompact:compact guidance injection:MED"
)

phase_coverage() {
  echo "## Phase 2: Coverage Analysis"
  echo ""

  if ! has_jq; then
    echo "> ⚠️  \`jq\` not found — install jq for coverage analysis."
    echo ""
    return
  fi

  # Collect all events covered
  covered_events=()
  for f in "$USER_SETTINGS" "$PROJECT_SETTINGS" "$LOCAL_SETTINGS"; do
    [ -f "$f" ] || continue
    while IFS= read -r ev; do
      covered_events+=("$ev")
    done < <(jq -r '.hooks // {} | keys[]' "$f" 2>/dev/null | tr -d '\r' || true)
  done

  echo "| Event | Covered | Risk if missing | Rating |"
  echo "|-------|---------|-----------------|--------|"

  for ev in "${KNOWN_EVENTS[@]}"; do
    covered="❌"
    for c in "${covered_events[@]}"; do
      [ "$c" = "$ev" ] && covered="✅" && break
    done

    case "$ev" in
      PreToolUse)   risk="Safety guards (yolo-guard, pre-commit)"; rating="HIGH" ;;
      PostToolUse)  risk="Response size injection, file formatting"; rating="MED" ;;
      Stop)         risk="Session cleanup, context guard"; rating="HIGH" ;;
      UserPromptSubmit) risk="Context pressure check"; rating="MED" ;;
      PreCompact)   risk="Compact guidance — prevents tool listing bloat"; rating="MED" ;;
      SessionStart) risk="Context injection, prompt-db loading"; rating="MED" ;;
      SessionEnd)   risk="Transcript forging, flywheel close"; rating="LOW" ;;
      *)            risk="—"; rating="LOW" ;;
    esac

    echo "| \`$ev\` | $covered | $risk | $rating |"
  done
  echo ""

  # Check for catch-all PostToolUse
  catch_all=$(for f in "$USER_SETTINGS" "$PROJECT_SETTINGS" "$LOCAL_SETTINGS"; do
    [ -f "$f" ] || continue
    jq -r '.hooks.PostToolUse // [] | .[] | select(.matcher == null or .matcher == "") | "found"' "$f" 2>/dev/null
  done | head -1)

  if [ -n "$catch_all" ]; then
    echo "> ⚠️  **Catch-all PostToolUse detected** (no matcher). This hook fires on every tool call."
    echo "> If it injects \`additionalContext\`, estimate: (tokens/fire) × (tool calls/session) = total overhead."
    echo ""
  fi
}

# ── phase 3: cost profiling ───────────────────────────────────────────────────

phase_cost() {
  echo "## Phase 3: Cost Profile"
  echo ""

  if ! has_jq; then
    echo "> ⚠️  \`jq\` not found — install jq for cost profiling."
    echo ""
    return
  fi

  echo "| Event | Matcher | Command | Est. fires/session | Exec time | Tier |"
  echo "|-------|---------|---------|-------------------|-----------|------|"

  for f in "$USER_SETTINGS" "$PROJECT_SETTINGS" "$LOCAL_SETTINGS"; do
    [ -f "$f" ] || continue
    extract_hooks "$f" "_" | while IFS=$'\t' read -r _src event matcher _type cmd _timeout; do
      # Estimate fires/session heuristically
      case "$event" in
        PreToolUse)      fires="~20" ;;
        PostToolUse)     fires="~50" ;;
        UserPromptSubmit) fires="~10" ;;
        Stop)            fires="1" ;;
        SessionStart)    fires="1" ;;
        SessionEnd)      fires="1" ;;
        PreCompact)      fires="0–2" ;;
        *)               fires="varies" ;;
      esac

      # Narrow matcher reduces fires
      [ "$matcher" != "(none)" ] && [ "$event" = "PostToolUse" ] && fires="~10"
      [ "$matcher" != "(none)" ] && [ "$event" = "PreToolUse" ] && fires="~10"

      # Time execution with empty payload
      exec_ms="—"
      if [[ "$cmd" == bash* ]] || [[ "$cmd" == /* ]] || [[ "$cmd" == ~* ]]; then
        expanded_cmd="${cmd/\~/$HOME}"
        # Extract script path: use $2 only when invoked via bash/sh, otherwise $1
        first_word=$(echo "$expanded_cmd" | awk '{print $1}')
        if [[ "$first_word" == "bash" ]] || [[ "$first_word" == "sh" ]]; then
          script_path=$(echo "$expanded_cmd" | awk '{print $2}')
        else
          script_path="$first_word"
        fi
        if [ -f "$script_path" ]; then
          start_ns=$(date +%s%N 2>/dev/null || echo 0)
          echo '{}' | eval "$expanded_cmd" >/dev/null 2>&1 || true
          end_ns=$(date +%s%N 2>/dev/null || echo 0)
          if [ "$start_ns" != "0" ] && [ "$end_ns" != "0" ]; then
            exec_ms=$(( (end_ns - start_ns) / 1000000 ))ms
          fi
        fi
      fi

      # Tier
      tier="🟢"
      case "$exec_ms" in
        *[0-9]ms)
          ms_val="${exec_ms%ms}"
          [ "$ms_val" -gt 500 ] 2>/dev/null && tier="🔴" || { [ "$ms_val" -gt 100 ] 2>/dev/null && tier="🟡"; }
          ;;
      esac
      [ "$fires" = "~50" ] && tier="🟡"

      short_cmd="${cmd:0:50}"
      [ "${#cmd}" -gt 50 ] && short_cmd="${short_cmd}…"
      echo "| \`$event\` | \`$matcher\` | \`$short_cmd\` | $fires | $exec_ms | $tier |"
    done
  done
  echo ""
}

# ── phase 4: verification ─────────────────────────────────────────────────────

phase_verify() {
  echo "## Phase 4: Verification"
  echo ""
  echo "| Event | Command | Exists | Exit(empty) | JSON valid | Timeout set | Status |"
  echo "|-------|---------|--------|-------------|------------|-------------|--------|"

  for f in "$USER_SETTINGS" "$PROJECT_SETTINGS" "$LOCAL_SETTINGS"; do
    [ -f "$f" ] || continue
    extract_hooks "$f" "_" | while IFS=$'\t' read -r _src event matcher _type cmd timeout; do

      # Check existence
      expanded="${cmd/\~/$HOME}"
      first_word=$(echo "$expanded" | awk '{print $1}')
      if [[ "$first_word" == "bash" ]] || [[ "$first_word" == "sh" ]]; then
        script=$(echo "$expanded" | awk '{print $2}')
      else
        script="$first_word"
      fi

      exists="❌"
      [ -f "$script" ] && exists="✅"
      # printf/echo built-ins pass automatically
      echo "$expanded" | grep -qE '^(printf|echo) ' && exists="✅(builtin)"

      # Exit code on empty stdin
      exit_code="—"
      if [ "$exists" = "✅" ]; then
        exit_code=$(echo '{}' | { eval "$expanded" >/dev/null 2>&1; echo $?; })
        [ "$exit_code" = "0" ] && exit_code="✅ 0" || exit_code="❌ $exit_code"
      fi

      # JSON validity
      json_valid="—"
      if [ "$exists" = "✅" ]; then
        out=$(echo '{}' | eval "$expanded" 2>/dev/null || true)
        if [ -n "$out" ]; then
          if has_python; then
            echo "$out" | py -m json.tool >/dev/null 2>&1 && json_valid="✅" || json_valid="❌ invalid"
          else
            json_valid="?(no python)"
          fi
        else
          json_valid="✅ (no output)"
        fi
      fi

      # Timeout
      timeout_ok="❌"
      [ "$timeout" != "unset" ] && timeout_ok="✅ ${timeout}s"

      # Overall status
      status="✅"
      [ "$exists" = "❌" ] && status="❌ missing"
      [[ "$exit_code" == ❌* ]] && status="⚠️ exit≠0"
      [[ "$json_valid" == ❌* ]] && status="⚠️ bad JSON"
      [ "$timeout_ok" = "❌" ] && status="${status} (no timeout)"

      short_cmd="${cmd:0:45}"
      [ "${#cmd}" -gt 45 ] && short_cmd="${short_cmd}…"
      echo "| \`$event\` | \`$short_cmd\` | $exists | $exit_code | $json_valid | $timeout_ok | $status |"
    done
  done
  echo ""
}

# ── summary ───────────────────────────────────────────────────────────────────

phase_summary() {
  echo "## Summary"
  echo ""

  total=0
  if has_jq; then
    for f in "$USER_SETTINGS" "$PROJECT_SETTINGS" "$LOCAL_SETTINGS"; do
      [ -f "$f" ] || continue
      count=$(extract_hooks "$f" "" | wc -l || echo 0)
      total=$((total + count))
    done
  fi

  echo "- Total hooks found: **$total**"
  echo "- Run \`audit.sh --phase=coverage\` to see gap ratings"
  echo "- Run \`audit.sh --phase=verify\` to check all hooks are reachable"
  echo "- Run \`audit.sh --phase=cost\` to flag expensive catch-alls"
  echo ""
  echo "_Generated: ${DATE}_"
}

# ── main ──────────────────────────────────────────────────────────────────────

echo "# Hook Audit Report — $DATE"
echo ""

case "$PHASE" in
  inventory) phase_inventory ;;
  coverage)  phase_coverage ;;
  cost)      phase_cost ;;
  verify)    phase_verify ;;
  all)
    phase_inventory
    phase_coverage
    phase_cost
    phase_verify
    phase_summary
    ;;
  *)
    echo "Unknown phase: $PHASE" >&2
    echo "Valid phases: inventory, coverage, cost, verify, all" >&2
    exit 1
    ;;
esac
