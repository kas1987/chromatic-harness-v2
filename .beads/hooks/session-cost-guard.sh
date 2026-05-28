#!/usr/bin/env bash
# session-cost-guard.sh — cumulative session cost/token alarm
#
# Complements context-guard.sh (which guards per-turn window). This guards the
# RUNAWAY-SESSION pattern that drove the 7-day cost spike: long /loop, /crank,
# /rpi sessions where context stays at 70% but cumulative spend balloons
# because a 150-200k cached prefix is re-read across 500-1000 turns.
#
# Emits stderr warnings (visible to model + user) at escalating thresholds.
# Never blocks. Read $HOME/.claude/CLAUDE.md "Session cost discipline" for policy.
#
# Thresholds (override via env):
#   SESSION_TURN_WARN          default 200    turns
#   SESSION_TURN_CRITICAL      default 500    turns
#   SESSION_TOKEN_WARN_M       default 25     million cumulative tokens
#   SESSION_TOKEN_CRITICAL_M   default 75     million cumulative tokens
#   SESSION_COST_WARN          default 10     USD (approximate, cache-read priced at $0.30/M, cache-create $3.75/M, output $15/M for sonnet)
#   SESSION_COST_CRITICAL      default 40     USD

set -u
TURN_WARN=${SESSION_TURN_WARN:-200}
TURN_CRIT=${SESSION_TURN_CRITICAL:-500}
TOK_WARN=$((${SESSION_TOKEN_WARN_M:-25} * 1000000))
TOK_CRIT=$((${SESSION_TOKEN_CRITICAL_M:-75} * 1000000))
COST_WARN=${SESSION_COST_WARN:-10}
COST_CRIT=${SESSION_COST_CRITICAL:-40}

INPUT=$(cat 2>/dev/null || true)
SESSION_ID=$(echo "$INPUT" | grep -oE '"session_id"\s*:\s*"[^"]*"' | head -1 | grep -oE '"[^"]*"$' | tr -d '"' || true)
[ -z "$SESSION_ID" ] && exit 0

SF=$(find "$HOME/.claude/projects" -name "${SESSION_ID}.jsonl" 2>/dev/null | head -1)
[ -z "$SF" ] || [ ! -f "$SF" ] && exit 0

# Sum usage across the whole session. Use node for speed/correctness on large files.
SUMMARY=$(node -e "
const fs=require('fs');
let turns=0, inT=0, outT=0, cacheR=0, cacheC=0;
const text=fs.readFileSync(process.argv[1],'utf8');
for(const ln of text.split('\n')){
  if(!ln) continue;
  let j; try{j=JSON.parse(ln);}catch{continue;}
  if(j.type!=='assistant') continue;
  const u=j.message&&j.message.usage; if(!u) continue;
  turns++;
  inT+=u.input_tokens||0; outT+=u.output_tokens||0;
  cacheR+=u.cache_read_input_tokens||0; cacheC+=u.cache_creation_input_tokens||0;
}
// Cost estimate at sonnet rates (the modal model). Opus would be ~3x.
const cost = (inT*3 + outT*15 + cacheR*0.30 + cacheC*3.75) / 1e6;
console.log(turns, inT+outT+cacheR+cacheC, cost.toFixed(2));
" "$SF" 2>/dev/null || echo "0 0 0.00")

TURNS=$(echo "$SUMMARY" | awk '{print $1}')
TOTAL=$(echo "$SUMMARY" | awk '{print $2}')
COST=$(echo "$SUMMARY" | awk '{print $3}')

[ "$TURNS" -lt 50 ] && exit 0  # don't spam early in session

# Threshold ladder. Highest tripped wins.
LEVEL=""
if   [ "$TURNS" -ge "$TURN_CRIT" ] || [ "$TOTAL" -ge "$TOK_CRIT" ] || awk "BEGIN{exit !($COST >= $COST_CRIT)}"; then
  LEVEL="CRITICAL"
elif [ "$TURNS" -ge "$TURN_WARN" ] || [ "$TOTAL" -ge "$TOK_WARN" ] || awk "BEGIN{exit !($COST >= $COST_WARN)}"; then
  LEVEL="WARN"
fi

[ -z "$LEVEL" ] && exit 0

# Format big numbers
fmt() { awk -v n="$1" 'BEGIN{
  if(n>=1e9) printf "%.2fB",n/1e9; else if(n>=1e6) printf "%.1fM",n/1e6; else if(n>=1e3) printf "%.1fK",n/1e3; else print n
}'; }

TT=$(fmt "$TOTAL")

if [ "$LEVEL" = "CRITICAL" ]; then
  printf '\n\033[1;31m[session-cost-guard CRITICAL]\033[0m session=%s turns=%d tokens=%s est_cost=$%s\n' "$SESSION_ID" "$TURNS" "$TT" "$COST" >&2
  printf '\033[1;31m  → This session has crossed a hard spend threshold. Consider:\n' >&2
  printf '    1. /handoff to summarize state and start a fresh session\n' >&2
  printf '    2. Stop any /loop or /crank that is running\n' >&2
  printf '    3. Downgrade to Sonnet if currently on Opus (especially Opus 4.7 1M context)\033[0m\n\n' >&2
else
  printf '\n\033[1;33m[session-cost-guard WARN]\033[0m session=%s turns=%d tokens=%s est_cost=$%s\n' "$SESSION_ID" "$TURNS" "$TT" "$COST" >&2
  printf '\033[1;33m  → Approaching session spend limits. Plan a handoff at a natural break.\033[0m\n\n' >&2
fi

exit 0
