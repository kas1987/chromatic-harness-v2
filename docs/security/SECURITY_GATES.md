# Security Gates (GH #57)

## Overview

Security gates prevent vulnerable code, exposed secrets, and unsafe dependencies
from reaching workflows or the main branch.  Three automated gates run as part of
the pre-push and CI pipeline:

1. **Secret scanning** — regex scan of tracked files for API keys, tokens, passwords
2. **Dependency audit** — `pip-audit` check of `requirements.txt` for known CVEs
3. **Service exposure audit** — local service bind-address check

## Gate: Secret Scanning

**Script:** `scripts/security_scan.py`

**What it detects:**

| Rule                   | Pattern                                      | Severity |
|------------------------|----------------------------------------------|----------|
| `credential_assignment`| `password =`, `api_key =`, etc. with value   | HIGH     |
| `private_key_block`    | `-----BEGIN ... PRIVATE KEY`                 | HIGH     |
| `github_pat`           | `ghp_` prefix (GitHub Personal Access Token) | HIGH     |
| `aws_access_key_id`    | `AKIA` prefix (AWS key)                      | HIGH     |
| `slack_token`          | `xox[baprs]-` prefix                         | HIGH     |

**Allowlist:** Lines containing `pragma: allowlist secret` are skipped.  Use this
for test fixtures or documentation examples that show key formats.

**Usage:**
```bash
python scripts/security_scan.py             # full scan
python scripts/security_scan.py --no-deps   # secrets only, skip pip-audit
python scripts/security_scan.py --json      # machine-readable JSON output
```

**Exit codes:**
- `0` — No high-severity findings
- `1` — One or more high-severity secrets detected

**Artifact:** `07_LOGS_AND_AUDIT/security/latest.json`

## Gate: Dependency Audit

**Runs as part of:** `scripts/security_scan.py` (unless `--no-deps`)

**Tool:** `pip-audit` (install with `pip install pip-audit`)

**Scope:** `requirements.txt` when present; ambient interpreter otherwise.

**Behavior when pip-audit is not installed:** Returns `status: not_instrumented`
rather than a false pass.  This is intentional — the gate degrades gracefully but
never pretends dependencies are clean.

**Install pip-audit:**
```bash
pip install pip-audit
```

**Run manually:**
```bash
python -m pip_audit -r requirements.txt -f json
```

## Gate: Log Integrity

**Script:** `scripts/log_integrity_check.py`

**What it checks:** SHA-256 hash chain over audit log files.  Detects any
post-write modification (tampering, truncation, line insertion).

**Usage:**
```bash
python scripts/log_integrity_check.py          # verify all chains
python scripts/log_integrity_check.py --build  # rebuild manifest
```

**Exit codes:**
- `0` — All chains intact
- `1` — Tampered or missing log detected

**Artifact:** `07_LOGS_AND_AUDIT/security/log_integrity_latest.json`

## Gate: Service Exposure

**Script:** `scripts/service_auth_audit.py`

**What it checks:** Local service bind addresses (Ollama, Neo4j, ChromaDB, ComfyUI).

**Exit codes:**
- `0` — No CRITICAL (0.0.0.0) exposure
- `1` — One or more services bound to all interfaces

**Artifact:** `07_LOGS_AND_AUDIT/security/service_auth_latest.json`

## Running All Gates Together

```bash
# Run all three security gates
python scripts/security_scan.py && \
python scripts/log_integrity_check.py && \
python scripts/service_auth_audit.py
echo "All security gates passed"
```

Or via the daily harness audit which includes these checks.

## Artifact Schema (latest.json)

`07_LOGS_AND_AUDIT/security/latest.json` — written by `security_scan.py`:

```json
{
  "secrets": {
    "status": "ok",
    "findings": [],
    "total": 0,
    "high_severity": 0
  },
  "dependencies": {
    "status": "not_instrumented",
    "high_severity": 0
  },
  "high_severity_total": 0,
  "passed": true,
  "timestamp": "20260601T120000Z"
}
```

## CI/Pre-Push Integration

Add to the SUITES list in `scripts/run-all-e2e.py` (see memory note: pre-push gate
only routes listed suites):

```python
SUITES = [
    ...
    "scripts/security_scan.py",
    "scripts/log_integrity_check.py",
]
```

Or wire directly in `.claude/settings.json` as a PrePush hook:

```json
{
  "hooks": {
    "PrePush": [
      { "command": "python scripts/security_scan.py" }
    ]
  }
}
```

## False Positive Handling

If a legitimate secret pattern (e.g. documentation example) triggers the scanner:

1. Add `# pragma: allowlist secret` to the end of the offending line
2. Re-run the scan to confirm the line is now ignored
3. Note the allowlist entry in a code comment explaining why it is safe

Never disable entire rules to work around a false positive.
