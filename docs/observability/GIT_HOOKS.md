# Git Hooks

`git_hooks/` is the **single canonical** hooks location (see
[`REPO_LAYERS.md`](../../REPO_LAYERS.md) §2). The legacy duplicate `hooks/` dir and the
`scripts/install_git_hooks.py` installer were retired in `8lri.5` — there is now one set,
not two.

## Active mechanism (preferred)

This repo points git directly at the tracked hooks via `core.hooksPath`, so no copy step
is needed and the hooks stay in sync with the tree:

```bash
git config core.hooksPath git_hooks
```

## Manual install (alternative)

If you prefer the default `.git/hooks/` location instead of `core.hooksPath`:

```bash
cp git_hooks/pre-commit .git/hooks/pre-commit
cp git_hooks/pre-push  .git/hooks/pre-push
chmod +x .git/hooks/pre-commit .git/hooks/pre-push
```

## What they run

- **pre-commit** — event-schema validation, file-collision detection, staged-only secret scan.
- **pre-push** — `py_compile` of `scripts/*.py` + observability-report generation.

> The CI-mirror gate (`scripts/ci_local.py`: ruff / format / mypy / pytest) is available as a
> **manual** tool — `python scripts/ci_local.py --stage pre-push` — and is enforced in CI
> (`.github/workflows/ci.yml`); it is intentionally not wired into the git hooks.
