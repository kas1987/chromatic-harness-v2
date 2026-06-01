# Secret Scanning Gate (OBS-009)

Secrets must never enter logs, docs, scripts, or generated artifacts. Two layers
enforce this:

| Layer | Tool | Scope |
|---|---|---|
| **pre-commit** | `scripts/scan_for_secrets.py --staged` | staged changes only |
| **CI** | `scripts/security_scan.py --no-deps` (observability workflow) | whole repo, tuned ruleset |
| **runtime redaction** | `scripts/redact_secrets.py` | excerpts before logging |

## What is detected

`redact_secrets.PATTERNS` (shared by the scanner and the redactor) covers:

- OpenAI tokens — `sk-...` and `sk-proj-...`
- GitHub tokens — `ghp_...`, `github_pat_...`
- Slack (`xox*`) and AWS access key ids (`AKIA...`)
- `Authorization: Bearer <token>` and `Cookie:` / `Set-Cookie:` headers
- Generic `api_key=`, `token=`, `secret=`, `password=` assignments
- PEM private-key blocks

## Pre-commit hook

Installed from `git_hooks/pre-commit`:

```bash
cp git_hooks/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
# or: git config core.hooksPath git_hooks
```

It scans only **staged** files (`--staged`), so a benign match elsewhere in the
tree never blocks an unrelated commit. A detected secret makes the commit fail.

## CI

The observability workflow (`.github/workflows/harness-observability-check.yml`)
runs `security_scan.py --no-deps` and **fails the build** on any high-severity
finding, so secrets cannot merge.

## Handling false positives

When the scanner flags a line that is genuinely not a secret (an example token,
a fixture, documentation), append an inline allowlist pragma to that line:

```python
api_key = "sk-not-a-real-key-just-an-example"   # pragma: allowlist secret
```

The scanner skips any line containing `pragma: allowlist secret`.

### Guidelines for safe allowlisting

- **Only allowlist the specific line**, never disable the whole scan.
- Prefer obviously-fake placeholders (`sk-EXAMPLE...`, `xxxxx`) over realistic
  strings, so reviewers can see at a glance it is not live.
- Put real example values in `.env.example` with placeholder content, never a
  real credential.
- If you must reference a real secret, store it in the environment / a secrets
  manager and read it at runtime — do not commit it, even allowlisted.
- Rotate immediately if a real secret is ever committed, even briefly.
