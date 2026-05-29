---
id: learning-2026-05-02-bats-hook-audit
type: learning
date: 2026-05-02
category: testing
confidence: high
maturity: confirmed
---

# Learning: Windows jq emits CRLF — strip it before string comparisons

**ID**: L1
**Category**: testing / shell

## What We Learned

`jq -r` on Windows/Git Bash outputs `\r\n` line endings. When reading into bash
variables via `IFS=$'\t' read`, the last field gets a trailing `\r`. This makes
`[ "$var" = "unset" ]` silently false when `$var` is actually `"unset\r"`.

Fix: pipe jq output through `tr -d '\r'` before any field-based processing.

## Why It Matters

The bug was invisible — `timeout_ok` silently got the wrong value, the
`(no timeout)` status flag never fired, and the test would have passed for the
wrong reason. CRLF issues don't produce errors; they produce wrong behavior.

## Source

hook-audit BATS suite — `verify_flags_missing_timeout` test failed in smoke-run.
Fix: `jq ... | tr -d '\r'` in `extract_hooks()` at `scripts/audit.sh:44`.

---

# Learning: `bash -n` does not validate BATS files

**ID**: L2
**Category**: testing / process

## What We Learned

BATS uses `@test "name" { ... }` syntax which is preprocessed by the bats runtime.
Running `bash -n file.bats` always fails with a syntax error on the `@test` line.
The correct BATS syntax check is `bats --dry-run file.bats` (requires bats installed)
or simply accept that BATS files cannot be syntax-checked via bash.

## Why It Matters

Plan conformance checks that specify `bash -n tests/hook-audit.bats` will always
fail even for a correct BATS file. Don't add `bash -n` to BATS file conformance.

## Source

Issue 3 conformance check in plan — discovered when `bash -n` returned exit 1.

---

# Learning: HOME override + cd pattern for scripts with hardcoded settings paths

**ID**: L3
**Category**: testing / architecture

## What We Learned

Scripts that read `$HOME/.claude/settings.json` and `.claude/settings.json` can
be isolated in tests by:
1. `export HOME=$(mktemp -d)` — redirects user settings reads
2. `cd $TEST_PROJECT` — redirects project-relative reads
3. Write fixture to `$TEST_HOME/.claude/settings.json` or `$TEST_PROJECT/.claude/settings.json`
4. Restore in teardown: `cd $_orig_pwd && rm -rf $TEST_HOME $TEST_PROJECT`

This is cleaner than env-var overrides because the script variables (`PROJECT_SETTINGS`,
`LOCAL_SETTINGS`) are set as local bash variables — they ignore environment overrides.

## Why It Matters

The alternative approach (exporting `PROJECT_SETTINGS=/nonexistent/...`) was used in
`audit.bats` from a prior session. It silently didn't work because `audit.sh` sets
`PROJECT_SETTINGS=".claude/settings.json"` as a local variable. Tests using that
approach would read the real project settings, giving non-deterministic results.

## Source

Vibe review caught the broken audit.bats isolation. HOME+cd pattern is correct.

---

# Learning: External linters can strip valid fixture fields mid-session

**ID**: L4
**Category**: process

## What We Learned

A post-file-write hook or external linter removed `"timeout": 5` from
`echo-no-timeout.json` during the session. The change was logged in a system
reminder but was easy to miss. Fixture files should be validated immediately after
writing with `python3 -m json.tool` and field-count checks.

## Why It Matters

If the linter had corrupted the fixture in a way that broke a test assertion (rather
than just removing an optional field), the smoke-test would have caught it. But
silent semantic changes to fixtures are hard to spot without checking expected fields.

## Source

`echo-no-timeout.json` system reminder during session. The `timeout: 5` removal
happened silently; test still passed because builtin detection doesn't depend on timeout.
