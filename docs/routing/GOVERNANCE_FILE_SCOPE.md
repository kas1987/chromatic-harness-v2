# FILE SCOPE Governance — Chromatic Harness v2

## Rule

Every worker, agent, or dispatched task **MUST NOT** write, create, or modify files outside its declared FILE SCOPE. Doing so will be detected by the orchestrator and reverted.

## Why

A single out-of-scope worker can:
- break previously passing test suites
- require multi-commit surgical revert
- burn significant recovery time
- contaminate files with hard-to-detect changes

## Enforcement

### Pre-Wave Baseline
Run `git diff --name-only HEAD~1` or count files before dispatch to establish a baseline.

### Worker Prompt Header
Every TaskCreate or dispatch prompt must include:

```
═══════════════════════════════════════════════════════════════
FILE SCOPE: <directory or file list>
═══════════════════════════════════════════════════════════════

You MUST NOT write, create, or modify files outside FILE SCOPE.
Doing so will be detected by the orchestrator and reverted.

Scope creep check: git diff --name-only HEAD~1 must be a subset
of the declared file manifest.
═══════════════════════════════════════════════════════════════
```

### Post-Wave Checks
1. `git diff --name-only HEAD~1` must be subset of declared manifest.
2. `pytest` (or equivalent) must pass before marking issues closed.
3. Broken test suite is the first signal of scope violation.

## Example Manifests

| Task | Valid Scope | Invalid Scope |
|---|---|---|
| Frontend console wave | `05_FRONTEND_CONSOLE/` | `02_RUNTIME/router/`, `09_DEPLOYMENT/config/` |
| Router core wave | `02_RUNTIME/router/` | `05_FRONTEND_CONSOLE/`, `08_PDRS/` |
| Config wave | `09_DEPLOYMENT/config/` | `02_RUNTIME/`, `03_AGENTS/` |
| Docs wave | `docs/`, `08_PDRS/` | Any runtime code |

## Remediation

If scope violation is detected:
1. Stop the worker immediately.
2. Revert contaminated files with `git checkout -- <paths>`.
3. Re-run tests to confirm baseline recovery.
4. Re-dispatch the task with stronger scope wording.
