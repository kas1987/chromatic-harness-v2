---
name: windows-crlf-in-jq-mapfile-pipelines
type: anti-pattern
confidence: 0.90
source_learnings: [2026-04-26-windows-crlf-in-jq-mapfile-pipelines]
description: Learning: Windows CRLF Silently Corrupts jq + mapfile Patterns
tags: [windows, bash, jq, mapfile, line-endings, gotcha]
---

# Learning: Windows CRLF Silently Corrupts jq + mapfile Patterns

## What We Learned

On Windows (Git Bash, WSL, or similar bash environments), `jq` output retains CRLF line endings even when the input JSON file uses LF. When you pipe `jq -r '.array[]'` into bash's `mapfile -t array`, every element ends with a stray `\r` character. Subsequent regex/grep operations against those patterns silently fail because the `\r` becomes part of the literal pattern string.

**Symptom:** Pattern array looks correct in declarations, but no matches ever fire. No error, just silent zero matches.

**Fix:** Add `tr -d '\r'` to the pipeline:

```bash
mapfile -t LOCAL_PATTERNS < <(jq -r '.local_patterns[]?' "${PATTERNS_FILE}" 2>/dev/null | tr -d '\r')
```

## Why It Matters

This is platform-invisible: tests pass on Linux/Mac, silently fail on Windows. A test suite that runs only on one platform won't catch the regression. The bug presents as "feature mysteriously stopped working after externalizing config" — easy to misdiagnose as a config-loading issue when it's actually a line-ending issue.

## Source

`hooks/model-router.sh` rt-nw-003 implementation (commit `8d41bb0`). Subagent caught the issue during smoke-testing on Windows; without the `tr -d '\r'` fix, all 11 tests passed individually (because the test harness pipes raw strings, not jq output) but real config-loaded patterns produced zero matches. Bash 5.2.37 confirmed.

## When To Apply

Anywhere you `mapfile`/`readarray` from a command pipeline on Windows:
- `jq -r '.array[]' file.json` — affected
- `awk` / `grep` / `sed` from text files with CRLF — affected
- `git log --pretty=...` — usually LF (git core.autocrlf doesn't affect log output)
- `find` — usually LF
- HTTP responses via `curl` — depends on server

**Defensive default:** add `| tr -d '\r'` to any `mapfile` source command on Windows-supporting code. Cheap, harmless on Linux/Mac (no CRs to strip).

## Detection Recipe

If patterns/array elements appear right but matches don't fire:

```bash
# Inspect raw bytes of first array element
printf '%s' "${MY_ARRAY[0]}" | od -c | head -3
```

If you see `\r` at the end, that's your bug.

## Related

- `tests/router-hook.sh` deliberately pipes literal string payloads to the hook (bypasses jq config-loading), so platform-specific bugs in config loading require manual smoke-test on each target OS to catch. Consider adding a CI matrix (Windows + Ubuntu) for hook tests if cross-platform reliability is required.
