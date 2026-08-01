# Plan: Recover CI from the unreachable `roach-pi` submodule pin

## Goal

Restore clean GitHub Actions checkouts on Linux and Windows by replacing the
unreachable `roach-pi` gitlink with a public immutable release commit.

## Invariant

The root repository references only a commit that exists on
`https://github.com/tmdgusya/roach-pi.git`; Actions credentials remain
unchanged and no test is skipped.

## Dependency-ordered slices

### SLICE-01 — Confirm the remote recovery target

- **Dependencies:** none
- **Allowed paths:** none (read-only)
- **Forbidden paths:** all writes
- **Gate:** `git ls-remote https://github.com/tmdgusya/roach-pi.git`
- **Expected proof:** `a2da093fd7cd00d1204b6c7eabc50245f71cde98` is reachable as
  `v1.38.0`.

### SLICE-02 — Replace the unreachable root gitlink

- **Dependencies:** SLICE-01
- **Allowed paths:** `02_RUNTIME/runtime-engines/roach-pi`
- **Forbidden paths:** `.github/workflows/`, application code, credentials,
  unrelated user edits
- **Gate:** `git ls-tree HEAD 02_RUNTIME/runtime-engines/roach-pi` plus a
  recursive submodule initialization from a clean checkout.
- **Expected proof:** checkout completes without `not our ref`.

### SLICE-03 — Verify, publish, and hand off

- **Dependencies:** SLICE-02
- **Allowed paths:** PDR, plan, handoff, bead state
- **Forbidden paths:** unrelated working-tree edits
- **Gate:** targeted local validation, guarded commit/push, and GitHub Actions
  run status for the pushed SHA.
- **Expected proof:** checkout jobs pass or any remaining failure is a new,
  post-checkout test failure with logs.

## Commands

```powershell
git ls-remote https://github.com/tmdgusya/roach-pi.git
git -C 02_RUNTIME/runtime-engines/roach-pi fetch origin --tags --depth=1 a2da093fd7cd00d1204b6c7eabc50245f71cde98
git -C 02_RUNTIME/runtime-engines/roach-pi checkout --detach a2da093fd7cd00d1204b6c7eabc50245f71cde98
git add 02_RUNTIME/runtime-engines/roach-pi 08_PDRS/PDR_HARNESS_CI_SUBMODULE_CHECKOUT_RECOVERY_2026-08-01.md .agents/plans/2026-08-01-roach-pi-ci-recovery.md 12_HANDOFFS/ROACH_PI_CI_CHECKOUT_HANDOFF_2026-08-01.md
git diff --cached --check
git commit -m "ci: pin roach-pi to reachable release commit"
git push origin codex/kimi-security
gh run list --branch codex/kimi-security --limit 5
```

## Completion state

- SLICE-01: complete; the old gitlink is missing and the `v1.38.0` commit is
  reachable.
- SLICE-02: in progress.
- SLICE-03: pending the implementation proof and Actions rerun.
