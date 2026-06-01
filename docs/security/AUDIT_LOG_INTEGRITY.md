# Audit Log Integrity (GH #85)

## Overview

The log integrity system provides tamper-evident protection for routing, dispatch,
and governance records using SHA-256 hash chaining.  Any modification to a log
entry — including insertion, deletion, or content change — produces a chain hash
mismatch that the verifier detects immediately.

## How the Hash Chain Works

Each JSONL log file is processed line by line.  The chain is computed as:

```
genesis_hash  = "0000...0000"  (64 zero characters)
entry_hash[n] = SHA-256(canonical_json(entry[n]))
chain_hash[n] = SHA-256(chain_hash[n-1] + entry_hash[n])
```

Where `canonical_json` re-encodes the entry with sorted keys and no extra
whitespace, making the hash independent of formatting differences.

The final `chain_hash` after processing all N entries is the manifest fingerprint
for that log file.  Storing this fingerprint and re-computing it later detects any
tampering.

## Covered Log Files

| Target key        | File path                                                   |
|-------------------|-------------------------------------------------------------|
| `telemetry`       | `05_REPORTS/telemetry.jsonl`                                |
| `token_governance`| `07_LOGS_AND_AUDIT/token_governance/history.jsonl`          |
| `drift_history`   | `07_LOGS_AND_AUDIT/drift/history.jsonl`                     |

## Usage

### Build the chain manifest (initial setup or after intentional log rotation)

```bash
python scripts/log_integrity_check.py --build
```

This reads all covered log files and writes the chain manifest to
`07_LOGS_AND_AUDIT/security/log_integrity_latest.json`.

### Verify integrity

```bash
python scripts/log_integrity_check.py
```

Exit code 0 = all chains intact.  Exit code 1 = tampered or missing file detected.

### Verify a single target

```bash
python scripts/log_integrity_check.py --target telemetry
```

### Machine-readable output

```bash
python scripts/log_integrity_check.py --json
```

## Manifest Schema

`07_LOGS_AND_AUDIT/security/log_integrity_latest.json`:

```json
{
  "schema_version": 1,
  "status": "ok",
  "tampered_count": 0,
  "total_checked": 3,
  "findings": [
    {
      "log_target": "telemetry",
      "status": "ok",
      "entry_count": 42,
      "chain_hash": "a1b2c3d4..."
    }
  ],
  "manifest_built_at": "20260601T120000Z",
  "timestamp": "20260601T130000Z"
}
```

Possible `status` values per finding:

| Status        | Meaning                                                  |
|---------------|----------------------------------------------------------|
| `ok`          | Chain intact — no tampering detected                    |
| `tampered`    | Chain hash mismatch — file was modified after manifest build |
| `missing`     | File was deleted after manifest build                    |
| `no_baseline` | No manifest exists yet; run `--build` first             |

## Detecting Tampering

When a file is tampered the verifier prints:

```
[TAMPERED] telemetry: 42 entries, chain=a1b2c3d4...
  expected: a1b2c3d4...
  actual:   deadbeef...
```

And exits with code 1, blocking any gate that calls this script.

## Integration Points

- **Pre-push gate**: Add `python scripts/log_integrity_check.py` to the CI/pre-push
  suite to block pushes that include log mutations without a manifest rebuild.
- **Daily audit**: Include in `scripts/daily_harness_audit.py` checks.
- **Closeout telemetry**: The `summarize()` pattern mirrors `security_scan.py` —
  call `log_integrity_check.run_verify()` and include result in session closeout.

## Limitations and Trust Model

- The manifest itself (`log_integrity_latest.json`) must be stored in a write-protected
  or separately audited location to be fully tamper-evident.  In the current setup it
  lives in the same repo; a committed hash in git history provides an external anchor.
- Hash chains protect against undetected post-hoc modification but not against a
  compromised process that rebuilds the chain after tampering.
- Log files are append-only by convention; the chain does not detect re-ordering of
  existing entries unless entry_count also changes.
