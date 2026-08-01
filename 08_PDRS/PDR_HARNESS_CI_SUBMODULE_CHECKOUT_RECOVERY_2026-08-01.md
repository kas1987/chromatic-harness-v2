# PDR: Harness CI Submodule Checkout Recovery

**Date:** 2026-08-01
**Status:** Implemented; validation follow-ups in progress
**Owner:** Codex
**Repository:** `kas1987/chromatic-harness-v2`
**Branch:** `codex/kimi-security`

## Decision summary

Repair the `roach-pi` submodule reference in the harness repository by pinning it
to the publicly reachable immutable commit for tag `v1.38.0`:

`a2da093fd7cd00d1204b6c7eabc50245f71cde98`

Do not point CI at the moving `main` branch, and do not modify the upstream
`tmdgusya/roach-pi` repository. The current root gitlink points to
`7eecdb3e2e75a250855eecddd0008ef6c5167b73`, which is not present on the upstream
remote and therefore cannot be fetched by a clean GitHub Actions runner.

## Evidence

- Failed run: https://github.com/kas1987/chromatic-harness-v2/actions/runs/30713121326
- Failed jobs: `test`, `Concurrency Suite (Windows, py3.11)`, and
  `Concurrency Suite (Windows, py3.12)`.
- Every job failed during `actions/checkout@v5` while recursively fetching
  `02_RUNTIME/runtime-engines/roach-pi`.
- GitHub reported: `upload-pack: not our ref 7eecdb3...`.
- The workflow's `Generate App token` step succeeded; authentication is not the
  failure cause.
- `tmdgusya/roach-pi` is publicly readable. Its reachable release commit is
  `a2da093...` (`v1.38.0`); its current `main` is `f6146ff...`.

## Goal and invariant

**Goal:** Make every clean Linux and Windows CI checkout able to initialize the
`roach-pi` submodule before tests begin.

**Invariant:** The superproject must reference an immutable commit that exists
on the configured submodule remote; no workflow credential or checkout bypass
may be introduced.

## Scope

### In scope

- Change only the root repository's gitlink for
  `02_RUNTIME/runtime-engines/roach-pi`.
- Add this PDR, its execution plan, and the shareable handoff.
- Verify the exact referenced commit is reachable and rerun GitHub Actions.

### Out of scope for the checkout-recovery slice

- Changing `actions/checkout`, permissions, secrets, or GitHub App credentials.
- Pushing to or rewriting `tmdgusya/roach-pi` (the current account has pull-only
  permission there).
- Updating the unrelated pre-existing working-tree edits.
- Changing GitHub App credentials or checkout behavior.

## Validation follow-ups discovered after checkout recovery

The first post-fix Actions run proved that all three jobs could fetch the
submodule, then exposed a separate Linux type-check failure. A second local
validation slice addressed those deterministic failures without changing the
credential or checkout design:

- Added explicit generic annotations at adapter, memory, scope, and API
  boundaries so both repository mypy commands pass under mypy 2.3.0.
- Accessed Windows-only `ctypes.windll` APIs portably so Linux type checking
  does not reject the module import path.
- Made API database tests use `asyncio.run`, which is portable across Python
  3.11 and 3.12 after pytest closes the default event loop.
- Aligned the remote Ollama C3 routing priority in both routing-table copies
  with the test contract used by CI.

These follow-ups are limited to type safety and test portability; they do not
alter authentication, secrets, checkout actions, or the upstream submodule.

## Acceptance criteria

1. `git ls-tree HEAD 02_RUNTIME/runtime-engines/roach-pi` resolves to
   `a2da093fd7cd00d1204b6c7eabc50245f71cde98` after the fix.
2. `git ls-remote https://github.com/tmdgusya/roach-pi.git` confirms that exact
   commit is reachable.
3. A fresh recursive checkout can initialize the submodule without
   `not our ref` or exit-code-128 errors.
4. GitHub Actions runs the test and Windows concurrency jobs past checkout.
5. The branch contains only the gitlink, the explicitly added PDR/plan/handoff
   artifacts, and the validation follow-up files described above; unrelated
   pre-existing working-tree edits remain uncommitted.

## Current implementation evidence

- Checkout-recovery commit: `172dccb32ce5be7fdb09298565918419c38eac63`.
- Run `30714398680` passed checkout on Linux and both Windows jobs, then
  failed only at the Linux mypy step; run `30714398688` passed.
- Local targeted validation after the follow-ups: `275 passed`.
- Local mypy validation: both repository mypy commands report no issues.
- The follow-up commit is being prepared and will be validated by a fresh
  Actions run before this PDR is marked complete.

## Rollback

Revert the single superproject commit. Do not restore the unreachable gitlink;
that would deterministically recreate the CI failure.

## Residual risk

The unpublished `7eecdb3` commit may contain changes not included in `v1.38.0`.
Because that commit is not available from the upstream remote and the current
account cannot push there, making it the CI reference is impossible. If those
changes are required, the upstream owner must publish them first; that is a
separate follow-up.
