# Handoff: CI checkout recovery for `roach-pi`

## Executive status

The unreachable submodule pin is fixed and pushed as
`172dccb32ce5be7fdb09298565918419c38eac63` on `codex/kimi-security`. The next
CI run fetched the submodule successfully in Linux and both Windows jobs. It
then exposed a separate Linux mypy failure, which has been fixed locally along
with two Python-version portability failures; the follow-up commit and Actions
confirmation are the remaining closeout gates.

This handoff is intended to be pasted into another LLM session if needed.

## Repository and authentication

- Repository: `kas1987/chromatic-harness-v2`
- Branch: `codex/kimi-security`
- GitHub CLI: authenticated as `kas1987`; scopes include `repo` and `workflow`.
- GitHub connector: repository permissions include admin, maintain, pull, push,
  and triage.
- Actions App authentication: generated successfully in run `30713121326`; it
  is not the cause of the failure.
- Follow-up checkout validation: run `30714398680` passed the submodule checkout
  in all three jobs; run `30714398688` passed.
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

## Follow-up validation completed locally

```powershell
python -m mypy src/ --config-file mypy.ini
python -m mypy 02_RUNTIME/router/ 02_RUNTIME/memory/ 02_RUNTIME/api/ --config-file mypy.ini
python -m ruff check 02_RUNTIME/api 02_RUNTIME/memory 02_RUNTIME/scope/enforcer.py 02_RUNTIME/router/context_detector.py src/chromatic_router/adapters tests/02_RUNTIME/api/test_api_db.py
python -m ruff format --check 02_RUNTIME/api 02_RUNTIME/memory 02_RUNTIME/scope/enforcer.py 02_RUNTIME/router/context_detector.py src/chromatic_router/adapters tests/02_RUNTIME/api/test_api_db.py
python -m pytest tests/test_api.py tests/test_auth.py tests/test_context_detector.py tests/test_memory_gate.py tests/test_system_memory.py tests/test_adapter_factory.py tests/test_router_gates.py tests/02_RUNTIME/api/test_api_endpoints.py tests/02_RUNTIME/api/test_api_db.py tests/02_RUNTIME/api/test_api_models.py tests/02_RUNTIME/memory/test_memory_modules.py -q
```

Results: both mypy commands passed, Ruff passed, and `275 passed` in the
targeted suite. The follow-up changes add explicit generic API/memory typing,
portable `ctypes.windll` access, `asyncio.run` in database tests, and remote
Ollama C3 priority in both routing-table copies.

## Third validation slice

Actions run `30715198094` passed checkout, type checking, lint, format, and
both Windows concurrency jobs. Its Linux full suite reached `4138 passed`,
`19 failed`, `1 skipped`, and `16 errors`; the failures were then reproduced
  in focused tests and fixed locally:

- API contract modules now isolate `AUTH_ENABLED=false` from the import-order
  side effect of the auth-enabled `test_api` module; production defaults are
  unchanged.
- CI seeds the ignored `.chromatic/active_writers.json` scaffold before the
  test job.
- Unpriced native-Claude usage remains `unknown` confidence, and telemetry
  tests key rows by model while preserving inferred `t_level` values.

The focused regression command now reports `40 passed`. Track the final
commit and replacement Actions run under bead `chromatic-harness-v2-59el`.

## Proof gates

1. Root tree points to `a2da093...`.
2. `git ls-remote` confirms the SHA exists upstream.
3. Fresh recursive clone initializes the submodule.
4. Actions gets past checkout on Linux and both Windows matrix jobs.
5. Any subsequent failure is evaluated as a real test failure, not a checkout
   or credential failure.

## Current tracked work

- Closed bead `chromatic-harness-v2-7bku`: unreachable submodule recovery.
- Closed bead `chromatic-harness-v2-bjjj`: mypy/type-check blockers.
- Closed bead `chromatic-harness-v2-70qi`: cross-platform routing and asyncio
  test blockers.
- In-progress bead `chromatic-harness-v2-59el`: remaining Linux full-suite
  contract failures; close it only after replacement CI is green.

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
