# CI Format Hygiene

Patterns that prevent recurring format-check CI failures on this repo.
Each entry has a corresponding self-healing test in `tests/test_repo_format_hygiene.py`.

---

## 1. Use `ruff format`, not `black`

The CI `test` job runs:

```yaml
- name: Format check
  run: ruff format --check src/ tests/
```

**Do not run `python -m black` before committing test files.**
`black` and `ruff format` produce subtly different output (trailing commas,
blank-line placement, import grouping).  Running `black` locally then pushing
will still fail the `ruff format --check` step on the runner.

### Correct pre-commit flow

```bash
python -m ruff format <changed files>
# then normalise to LF (see §2)
```

Local gate (`ci_local.py` "pre-commit") runs both `ruff check` and
`ruff format` — use it to catch this before pushing:

```bash
python scripts/ci_local.py pre-commit
```

---

## 2. Python files must be LF on all platforms

Windows `core.autocrlf=true` (default) injects CRLF into files on checkout.
The Linux CI runner then sees CRLF and `ruff format --check` reformats them,
causing spurious failures even when the file content is logically unchanged.

**Fix (already in repo):** `.gitattributes` pins `*.py` to LF:

```
*.py text eol=lf
```

If you ever create a new `.gitattributes` or merge from a fork that removes this
line, the self-healing test `test_gitattributes_pins_python_to_lf` will catch it
before it reaches CI.

### After running ruff on Windows

Ruff may output CRLF on Windows.  After formatting, normalise before staging:

```powershell
$f = "path\to\file.py"
$t = [System.IO.File]::ReadAllText($f).Replace("`r`n","`n")
[System.IO.File]::WriteAllText($f, $t, [System.Text.UTF8Encoding]::new($false))
```

---

## 3. Bash hook scripts must also be LF

`.gitattributes` pins hook directories to LF:

```
git_hooks/** text eol=lf
hooks/**      text eol=lf
.beads/hooks/** text eol=lf
```

A CRLF shebang (`#!/usr/bin/env bash\r`) is invisible in editors but causes
`/usr/bin/env: 'bash\r': No such file or directory` at runtime on the CI runner
and locally under Git Bash.

---

## 4. Anthropic adapter: system message extraction

The Anthropic API rejects `role:system` entries inside the `messages=` list.

**Pattern (implemented in `anthropic_adapter.py`):**

- Filter ALL system messages out of the message list (any position, not just index 0).
- Merge their text content and pass as `system=[{"type":"text","text":...,"cache_control":{"type":"ephemeral"}}]`.
- Handle both `str` and `list-of-blocks` system content formats.
- If no non-system messages remain after filtering, fall back to `req.objective`.
- Surface `cache_read_input_tokens` / `cache_creation_input_tokens` from the
  response usage object as `RouteUsage.cache_read_tokens` / `cache_write_tokens`.

Covered by `TestAnthropicAdapterCaching` (7 tests) in
`tests/02_RUNTIME/router/adapters/test_anthropic_adapter.py`.

---

## 5. Governance CI installer exit

`harness-governance.yml` installs `bd` via a shell pipe.  The installer exits 1
when Go is installed to a non-standard path (e.g. `$HOME/go/bin`) and that path
isn't in `$PATH` yet.  With `set -euo pipefail` this kills the step before the
`$PATH` update loop runs.

**Fix:** suffix the installer line with `|| true`:

```yaml
- name: Install beads (bd)
  run: curl -fsSL https://... | bash || true
```

The subsequent PATH-loop step then adds the install dir and `bd` becomes
available for later steps.
