# Handoff: CI checkout recovery for `roach-pi`

## Executive status

The Security branch's application fixes are already committed and pushed as
`7aba1d3` on `codex/kimi-security`. The next CI run fails before any test runs:
all three CI jobs cannot fetch the `roach-pi` submodule.

This handoff is intended to be pasted into another LLM session if needed.

## Repository and authentication

- Repository: `kas1987/chromatic-harness-v2`
- Branch: `codex/kimi-security`
- GitHub CLI: authenticated as `kas1987`; scopes include `repo` and `workflow`.
- GitHub connector: repository permissions include admin, maintain, pull, push,
  and triage.
- Actions App authentication: generated successfully in run `30713121326`; it
  is not the cause of the failure.
- Upstream submodule repository: `tmdgusya/roach-pi`; current account has
  pull-only permission there.

## Failure evidence

Run: https://github.com/kas1987/chromatic-harness-v2/actions/runs/30713121326

The failure is:

```text
fatal: remote error: upload-pack: not our ref 7eecdb3e2e75a250855eecddd0008ef6c5167b73
Fetched in submodule path '02_RUNTIME/runtime-engines/roach-pi', but it did not contain 7eecdb3...
The process 'git.exe' failed with exit code 128
```

The root gitlink currently resolves to the missing SHA:

```text
160000 commit 7eecdb3e2e75a250855eecddd0008ef6c5167b73 02_RUNTIME/runtime-engines/roach-pi
```

The remote exposes:

- `v1.38.0`: `a2da093fd7cd00d1204b6c7eabc50245f71cde98`
- `main`: `f6146ffa9a46e6097349151981d160c7c6de23d6`

## Approved decision

Pin the root gitlink to the immutable public `v1.38.0` commit
`a2da093fd7cd00d1204b6c7eabc50245f71cde98`. Do not use moving `main`, change
Actions credentials, or rewrite the upstream repository.

## Exact execution

```powershell
git -C 02_RUNTIME/runtime-engines/roach-pi fetch origin --tags --depth=1 a2da093fd7cd00d1204b6c7eabc50245f71cde98
git -C 02_RUNTIME/runtime-engines/roach-pi checkout --detach a2da093fd7cd00d1204b6c7eabc50245f71cde98
git add 02_RUNTIME/runtime-engines/roach-pi 08_PDRS/PDR_HARNESS_CI_SUBMODULE_CHECKOUT_RECOVERY_2026-08-01.md .agents/plans/2026-08-01-roach-pi-ci-recovery.md 12_HANDOFFS/ROACH_PI_CI_CHECKOUT_HANDOFF_2026-08-01.md
git diff --cached --check
git commit -m "ci: pin roach-pi to reachable release commit"
git push origin codex/kimi-security
```

Then monitor:

```powershell
gh run list --repo kas1987/chromatic-harness-v2 --branch codex/kimi-security --limit 5
gh run watch <run-id> --exit-status
```

## Proof gates

1. Root tree points to `a2da093...`.
2. `git ls-remote` confirms the SHA exists upstream.
3. Fresh recursive clone initializes the submodule.
4. Actions gets past checkout on Linux and both Windows matrix jobs.
5. Any subsequent failure is evaluated as a real test failure, not a checkout
   or credential failure.

## Do not touch

Preserve these pre-existing local edits:

- `12_HANDOFFS/PRE_SESSION_INVENTORY.md`
- `config/pre_session/inventory.snapshot.json`
- `config/routing/privacy-policy.yaml`
- `docs/PRE_SESSION_AND_TOOLS.md`
- `tests/test_kimi_and_governance.py`

The checked-out submodule also has a local, unstaged overlay edit at
`02_RUNTIME/runtime-engines/roach-pi/extensions/agentic-harness/discipline.ts`.
It matches the unpublished `7eecdb3` overlay and must not be cleaned or staged
as part of this repair.

## Residual follow-up

If behavior from unpublished commit `7eecdb3` is required, ask the upstream
`roach-pi` owner to publish that commit or create a reachable release. Do not
restore the missing gitlink in this repository.
