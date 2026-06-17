---
id: learning-2026-06-03-ruff-format-not-black-ci-gate
type: learning
name: 2026-06-03-ruff-format-not-black-ci-gate
confidence: 0.95
source: chromatic-harness-v2 session 2026-06-03 (PR #259 format failures)
date: 2026-06-03
status: candidate
---

# CI format gate uses `ruff format`, not `black` — they produce different output

## Observation

Two separate pushes on PR #259 were wasted on format commits because the local
workflow used `python -m black` while the CI `test` job runs
`ruff format --check src/ tests/`.  These two formatters produce subtly
different output (trailing commas, blank-line rules, import grouping), so a file
that `black` calls clean may still be flagged by `ruff format --check`.

Compound issue: Windows `core.autocrlf=true` injects CRLF into Python files on
checkout. The Linux CI runner then sees CRLF and `ruff format --check` treats
those files as "needing reformatting".  Even after running ruff on Windows, the
output file may be CRLF again — requiring an explicit LF normalisation step
before staging.

## Root causes

1. **Wrong formatter**: `black` ≠ `ruff format` output.
2. **CRLF on Windows**: no `*.py text eol=lf` rule in `.gitattributes` meant
   Windows autocrlf was free to corrupt Python files on every checkout.

## Fixes applied (PR #259)

- `.gitattributes` now contains `*.py text eol=lf` — permanent CRLF lock.
- `docs/CI_FORMAT_HYGIENE.md` documents the correct pre-commit flow.
- `tests/test_repo_format_hygiene.py` guards both fixes with self-healing
  assertions (registered in `run-all-e2e.py` SUITES).

## Recommended pre-commit flow (Windows)

```bash
# 1. Format with the same tool CI uses
python -m ruff format <changed files>

# 2. Normalise to LF (ruff may write CRLF on Windows)
$f = "path\to\file.py"
$t = [System.IO.File]::ReadAllText($f).Replace("`r`n","`n")
[System.IO.File]::WriteAllText($f, $t, [System.Text.UTF8Encoding]::new($false))

# 3. Verify
python -m ruff format --check <changed files>
```

Or use the local gate runner which does both ruff checks:

```bash
python scripts/ci_local.py pre-commit
```

## Self-healing coverage

`tests/test_repo_format_hygiene.py` asserts:
- `.gitattributes` contains `*.py text eol=lf`
- `.github/workflows/ci.yml` uses `ruff format --check` (not black)
- Hook dirs are pinned to `eol=lf`

These tests are in the pre-push SUITES gate so any regression is caught before
the branch reaches CI.
