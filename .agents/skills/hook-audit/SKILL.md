---
name: hook-audit
description: Audit Claude Code hook configuration across 4 phases: inventory, coverage, cost profiling, and verification. Generates a markdown report. Use before adding new hooks or when diagnosing unexpected behavior.
---

# Hook Audit

> **Quick Ref:** `bash .claude/skills/hook-audit/scripts/audit.sh` — full 4-phase report to stdout.

**YOU MUST EXECUTE THIS WORKFLOW. Do not just describe it.**

## Quick Reference

### Hook Event Catalog

| Event | Trigger | Stdin payload |
|-------|---------|---------------|
| `SessionStart` | Session opens | `{}` |
| `PreToolUse` | Before every tool call | `{session_id, tool_name, tool_input}` |
| `PostToolUse` | After successful tool | `{session_id, tool_name, tool_input, tool_response}` |
| `PostToolUseFailure` | After failed tool | `{session_id, tool_name, tool_input, error}` |
| `UserPromptSubmit` | User submits message | `{session_id, prompt}` |
| `Stop` | Claude stops | `{session_id}` |
| `PreCompact` | Before compaction | `{session_id, type}` |
| `PostCompact` | After compaction | `{session_id, summary}` |
| `Notification` | On notification | `{session_id, message}` |
| `SessionEnd` | Session ends | `{session_id}` |

### Token Cost Tiers

| Tier | Execution time | additionalContext injected | When to flag |
|------|---------------|--------------------------|--------------|
| 🟢 Fast | < 100ms | 0 tokens | — |
| 🟡 Medium | 100–500ms | < 200 tokens | catch-all PostToolUse |
| 🔴 Heavy | > 500ms | > 200 tokens | blocks tool pipeline |

**Per-session cost formula:** `(hook fires/session) × (tokens injected per fire)`

A catch-all PostToolUse injecting 100 tokens × 50 tool calls = **5,000 tokens/session overhead**.

### Valid JSON Output Fields

```json
{
  "systemMessage": "Shown in UI to user (all hooks)",
  "continue": false,
  "stopReason": "Message shown when continue=false",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "Text injected into model context"
  }
}
```

### Anti-Patterns

| Pattern | Risk | Fix |
|---------|------|-----|
| No `timeout` field | Hook blocks indefinitely | Set `"timeout": N` always |
| `\|\| true` everywhere | Silent failures mask broken hooks | Remove for blocking hooks; keep for advisory |
| Hardcoded absolute paths | Fails on other machines | Use `~` expansion or repo-relative paths |
| Catch-all PostToolUse with heavy output | Injects context on every tool call | Add matcher or suppress for small responses |
| `additionalContext` unconditionally | Context bloat every turn | Gate on threshold (e.g. only inject on error) |
| Missing stdin handling | Hook crashes on empty payload | Always `INPUT=$(cat)` before processing |
| Same hook in both global and project | Fires twice per event — double latency | Keep in global only; project uses relative paths only for project-local scripts |
| Credentials in settings.json `env` block | Token exposed in file, backup, and git | Move to OS-level env or a secrets manager |

---

## 4-Phase Workflow

### Phase 1: Inventory

Enumerate every hook configuration from all settings files in load order.

**Load order (later overrides earlier):**
1. `~/.claude/settings.json` (user-global)
2. `.claude/settings.json` (project — committed)
3. `.claude/settings.local.json` (project — gitignored, personal)

**Steps:**
1. Check which of the three settings files exist
2. For each file: extract every hook entry — event, matcher, command, type, timeout
3. Note source file for each hook
4. **Cross-file dedup check:** For each event+matcher pair, flag if both global AND project settings define it. Any duplicate fires twice per event — double latency. Project settings should only add project-local scripts not present in global.
5. Run `audit.sh --phase=inventory`

**Deliverable:** Combined hook registry table.

```
| Source file | Event | Matcher | Command (truncated) | Timeout |
```

**Done when:** Every hook from every settings file is in the registry.

---

### Phase 2: Coverage Analysis

Compare your hook registry against the full event catalog and identify gaps.

**Steps:**
1. For each event in the catalog: does at least one hook cover it?
2. For `PostToolUse` catch-alls (no matcher): flag — fires on every tool
3. For `PreToolUse` on `Bash`: verify a safety guard is present
4. Rate each gap: HIGH (breaks safety/quality), MED (missed optimization), LOW (nice-to-have)

**Coverage gaps to flag:**

| Missing hook | Risk | Rating |
|-------------|------|--------|
| No `Stop` hook | No session cleanup, no context guard | HIGH |
| No `PreCompact` guidance | Compact summary bloats with tool listings | MED |
| No `UserPromptSubmit` guard | No context pressure check before turns | MED |
| No `PreToolUse` Bash guard | Safety-critical commands unguarded | HIGH |
| PostToolUse catch-all, no size guard | Unbounded response token injection | MED |

**Run:** `audit.sh --phase=coverage`

**Done when:** All events assessed, each gap rated HIGH/MED/LOW.

---

### Phase 3: Cost Profiling

Estimate per-session token overhead for every hook.

**Steps:**
1. For each hook: determine expected fires per session (catch-all = high; specific matcher = low)
2. For `PostToolUse` hooks: estimate `additionalContext` tokens injected per fire
3. Time each hook: `time echo '{}' | bash <hook-command> 2>/dev/null`
4. Flag hooks where `(fires/session × tokens/fire) > 500`

**Estimation heuristics:**
- `PreToolUse` Bash guard: fires every Bash call (~20/session) — keep under 50ms
- `PostToolUse` catch-all: fires every tool call (~50/session) — injecting > 100 tokens = 5k overhead
- `Stop`: fires once/session — can be heavier

**Run:** `audit.sh --phase=cost`

**Done when:** Every hook has estimated fires/session, tokens/fire, execution-time.

---

### Phase 4: Verification

Smoke-test every hook and validate its output.

**Per-hook checklist:**
- [ ] Script/binary exists at the specified path (`test -f <path>`)
- [ ] Handles empty stdin without crash: `echo '{}' | bash <cmd>; echo "exit: $?"`
- [ ] Exit code 0 for no-op input (unless intentionally blocking)
- [ ] JSON output is well-formed: `... | python -m json.tool >/dev/null`
- [ ] `hookEventName` matches the event (if `hookSpecificOutput` used)
- [ ] `timeout` is set and appropriate for the event type

**Timeout guide:**
- `PreToolUse`: ≤ 10s (blocks tool execution)
- `PostToolUse`: ≤ 10s (blocks next turn)
- `Stop`: ≤ 30s (acceptable post-session cleanup)
- `SessionStart`/`SessionEnd`: ≤ 15s

**Security check — credentials in settings files:**
- Scan the `env` block of every settings file for credential-pattern keys:
  ```bash
  python3 -c "
  import json, re, sys
  for path in ['$HOME/.claude/settings.json', '.claude/settings.json', '.claude/settings.local.json']:
      try:
          env = json.load(open(path)).get('env', {})
          for k,v in env.items():
              if re.search(r'token|key|secret|password|pat|credential', k, re.I):
                  print(f'WARN {path}: {k} = {str(v)[:20]}...')
      except: pass
  "
  ```
- Any credential-like value in `env` should be moved to OS-level env (`.zshrc`, `.bashrc`, or Windows user env variables). Settings files can be backed up, synced, or accidentally committed.

**Run:** `audit.sh --phase=verify`

**Done when:** Every hook has been smoke-tested and results recorded.

---

## Design Checklist (for new hooks)

Before adding any hook, answer each question:

- [ ] **Event:** Which event triggers this? Is it the right one?
- [ ] **Matcher:** Is it as specific as possible? (avoid catch-all PostToolUse)
- [ ] **Timeout:** What's the worst-case execution time? Set `timeout` 2× that.
- [ ] **Stdin:** Does it read stdin? Use `INPUT=$(cat)` at the top — never inline pipe.
- [ ] **Output:** Does it inject `additionalContext`? Estimate tokens × fires/session.
- [ ] **Blocking:** Should it block on error? Only set `continue: false` if truly needed.
- [ ] **Paths:** Uses `~` or repo-relative? Test on a clean clone.
- [ ] **Silent failure:** Does `|| true` hide real errors? Remove for safety hooks.
- [ ] **Conflicts:** Does it overlap with an existing hook on the same event+matcher?
- [ ] **Portability:** Works on Windows (Git Bash/PowerShell) if this is a Windows project?

---

## Running the Audit

```bash
# Full report (all 4 phases)
bash .claude/skills/hook-audit/scripts/audit.sh

# Single phase
bash .claude/skills/hook-audit/scripts/audit.sh --phase=inventory
bash .claude/skills/hook-audit/scripts/audit.sh --phase=coverage
bash .claude/skills/hook-audit/scripts/audit.sh --phase=cost
bash .claude/skills/hook-audit/scripts/audit.sh --phase=verify

# Save report
bash .claude/skills/hook-audit/scripts/audit.sh > hook-audit-$(date +%Y%m%d).md
```

## E2E Test Suite

The harness includes a bats test suite that live-fires all hooks and verifies behaviour end-to-end. Run this before pushing or after changing any hook.

```bash
# Run all suites (hook-audit + model-router + dispatch + settings)
export PATH="$HOME/.local/bin:$PATH"
bash ~/.claude/hooks/tests/run-all-e2e.sh
```

Exit 0 = all suites pass. Exit non-zero = at least one test failed.

Output example:
```
--- hook-audit ---
1..17  ok 1 … ok 17 all_phases_runs_all_headings

--- model-router ---
1..20  ok 1 … ok 20 missing patterns file → safe fallback tier-4 Claude

==================================================
HARNESS E2E -- ALL SUITES
==================================================
  PASS  [17/17]  hook-audit
  PASS  [20/20]  model-router
  PASS  [15/15]  multi-provider-dispatch
  PASS  [10/10]  harness-settings
--------------------------------------------------
  Total pass: 62   Total fail: 0
==================================================
```

**Suite locations:**

| Suite | File | Tests |
|-------|------|-------|
| hook-audit | `~/.claude/skills/hook-audit/tests/hook-audit.bats` | 17 |
| model-router | `~/.claude/hooks/tests/model-router.bats` | 20+ |
| multi-provider-dispatch | `~/.claude/hooks/tests/multi-provider-dispatch.bats` | 15 |
| harness-settings | `~/.claude/hooks/tests/harness-settings.bats` | 10+ |

**pre-push gate:** `~/.claude/hooks/pre-push.sh` calls `run-all-e2e.sh` automatically on every push. A push is blocked if any suite fails.

**Install bats (one-time):**
```bash
bash ~/.claude/skills/hook-audit/tests/install-bats.sh
# or: npm install -g bats
```

## Harness Map

Generate a visual flow diagram of your hook configuration:

```bash
# Render the template (requires Graphviz)
dot -Tsvg .claude/skills/hook-audit/references/flow.dot.template -o hook-flow.svg

# Or PNG
dot -Tpng .claude/skills/hook-audit/references/flow.dot.template -o hook-flow.png
```

See `references/flow.dot.template` for the annotated template and color-coding guide.

## Examples

### Full audit
```
/hook-audit
```
Expected: Runs all 4 phases (inventory, coverage, cost, verify), outputs report with hook count, gaps, and cost estimate.

### Single phase — coverage only
```bash
bash .claude/skills/hook-audit/scripts/audit.sh --phase=coverage
```
Expected: Lists which events have hooks vs. which are unguarded.

### Save dated report
```bash
bash .claude/skills/hook-audit/scripts/audit.sh > hook-audit-$(date +%Y%m%d).md
```
Expected: Full audit written to `hook-audit-20260521.md`.

### Render harness flow diagram
```bash
dot -Tsvg .claude/skills/hook-audit/references/flow.dot.template -o hook-flow.svg
```
Expected: SVG diagram of hook event flow with color-coded nodes.

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `audit.sh` not found | Script missing or wrong path | Confirm `~/.claude/skills/hook-audit/scripts/audit.sh` exists; re-install skill if absent |
| `dot` command not found | Graphviz not installed | Install Graphviz: `winget install graphviz` (Windows) or `brew install graphviz` (Mac) |
| Coverage phase shows 0 hooks | `settings.json` not found at expected path | Verify `~/.claude/settings.json` exists; audit.sh reads from that path |
| Cost estimate is 0 | Hook timeout values missing from settings | Ensure all hooks have `"timeout"` fields set in settings.json |
| Audit report blank | Phase script exited non-zero silently | Run with `bash -x audit.sh` to trace execution and identify the failing step |
