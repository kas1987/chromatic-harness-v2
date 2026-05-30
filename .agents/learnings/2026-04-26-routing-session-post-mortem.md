---
id: learning-2026-04-26-routing-session
type: learning
date: 2026-04-26
category: process
confidence: high
maturity: confirmed
source: post-mortem/routing-session
---

# Learning: Unrelated Git Histories — Force Push as Clean Resolution

**Category**: process
**Confidence**: high

## What We Learned

When two branches share no common ancestor (`merge-base` returns nothing), merge and rebase both fail.
The only clean options are force-push (local wins) or cherry-pick (selective import).
Force-push is correct when the local tree is the canonical live system and the remote drifted into an
unreconciled experiment. Always confirm with the user before executing — it's irreversible.

## Why It Matters

Rebase and merge both appear to work until they hit the "refusing to merge unrelated histories" wall.
Knowing the force-push path upfront saves the stash/abort/restore cycle.

## Source

Routing session 2026-04-26 — kas1987/claude-config had unrelated histories (local: 39 commits, remote: 24,
no common ancestor). Local CLAUDE.md was the live system; force push was the correct call.

---

# Learning: Atomic Shell Log Rotation for JSONL Files

**Category**: architecture
**Confidence**: high

## What We Learned

For append-only JSONL logs in shell hooks, rotate with `tail -n keep > tmp && cp tmp log && rm tmp`.
Using `>` to truncate in-place is not atomic. The `mv` pattern fails when src/dst are on different
devices (Windows/WSL). `cp + rm` is portable and effectively atomic for small log sizes.

`MAX_LOG_LINES` via env var (with a `:-default` fallback in the script) keeps configuration
at the call site without touching the hook logic.

## Why It Matters

Log rotation in a PreToolUse hook must never block or fail-loud. The `cp + rm` pattern
degrades gracefully and is safe to run inside a hook that always exits 0.

## Source

rt-nw-004 — model-router.sh log rotation, 2026-04-26. `mv` failed with "Device or resource busy"
during log cleanup; `cp /tmp/... ~/.claude/...` succeeded.

---

# Learning: settings.json env Section Passes Vars to Hooks at Session Start

**Category**: architecture
**Confidence**: high

## What We Learned

Claude Code's `settings.json` supports an `"env"` object. Variables defined there are injected
into the shell environment that runs hooks. This is the right mechanism for configuring hook
behavior without requiring the user to set shell env vars manually.

```json
{ "env": { "ROUTER_MAX_LOG_LINES": "500" } }
```

All values must be strings (JSON schema constraint). The hook reads them with `${VAR:-default}`.

## Why It Matters

Avoids per-shell `export` instructions in docs. The setting is version-controlled with the rest of
the config and applies to all hooks in the session without any additional wiring.

## Source

ROUTER_MAX_LOG_LINES=500 wired via settings.json, 2026-04-26.

---

# Learning: consumer.position = Byte-Offset Cursor for Tail-Follow Consumers

**Category**: architecture
**Confidence**: medium

## What We Learned

`.agents/router/consumer.position` holds a raw byte offset (e.g., `3231`). This is the OL layer's
read cursor — it stores how far into `log.jsonl` the consumer has already processed, enabling
incremental reads without re-scanning the full file.

Any tool that rotates or rewrites the log file must reset or recalculate this cursor, or the
consumer will seek past EOF and stall.

## Why It Matters

Log rotation that rewrites `log.jsonl` (not appends) must also update `consumer.position` to 0
or the new file size. The current rotation (`tail + cp`) shrinks the file, so after rotation
`consumer.position` will be > actual file size until the consumer resets it.

## Source

Observed during post-mortem 2026-04-26. consumer.position=3231; post-rotation file was smaller.
