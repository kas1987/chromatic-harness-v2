# harness_run.py — Terminal Command Wrapper (OBS-005)

`scripts/harness_run.py` wraps any shell command so that **failures become
observable**. It:

1. Runs the command and streams its stdout/stderr through unchanged.
2. **Preserves the original exit code** — callers and CI see the real result.
3. On non-zero exit, writes a **redacted** `command_result` event to
   `00_META/observability/ERROR_LOG.jsonl` (secrets are scrubbed before logging).
4. Optionally routes the event to incident/collision/queue artifacts (`--route`).

A missing binary (`FileNotFoundError`) is also treated as a failure: it logs a
`command_not_found` event and returns the conventional exit code **127**.

## Invocation

```
python scripts/harness_run.py [options] -- <command> [args...]
```

Everything after `--` is the command to run. The `--` separator is recommended
so wrapper flags are never confused with the wrapped command's flags.

### Options

| Flag | Default | Purpose |
|---|---|---|
| `--repo-root PATH` | auto-detected | Repo root / working dir for the command. |
| `--surface NAME` | `terminal` | Logged event `source.surface`. |
| `--agent NAME` | `""` | Logged agent identity. |
| `--model NAME` | `""` | Logged model identity. |
| `--session-id ID` | `""` | Correlate events to a session. |
| `--severity-on-fail` | `medium` | Severity stamped on failure events. |
| `--category-on-fail` | `command_failure` | Category stamped on failure events. |
| `--route` | off | Route the failure event after logging. |

## Sample usage

### npm

```bash
# Build; a failed build is logged with a redacted excerpt.
python scripts/harness_run.py -- npm run build

# Install with elevated severity and routing.
python scripts/harness_run.py --severity-on-fail high --route -- npm ci
```

### python

```bash
# Run a script and capture any traceback on failure.
python scripts/harness_run.py -- python scripts/migrate.py --apply

# Tag the surface/agent so events are attributable.
python scripts/harness_run.py --surface ci --agent chainbreaker -- python -m mypackage
```

### pytest

```bash
# Log test failures (non-zero exit) to the error log and route them.
python scripts/harness_run.py --category-on-fail test_failure --route -- pytest -q tests/

# A single targeted test.
python scripts/harness_run.py -- pytest -q tests/test_event_routing.py
```

### shell

```bash
# Chained shell commands — wrap with `bash -c` so the whole pipeline is one command.
python scripts/harness_run.py -- bash -c "make lint && make test"

# On Windows runners, the equivalent via cmd/pwsh:
python scripts/harness_run.py -- pwsh -NoProfile -Command "ruff check . ; pytest -q"
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Command succeeded — nothing logged. |
| `2` | No command supplied to the wrapper. |
| `127` | Command binary not found (`command_not_found` event logged). |
| _other_ | The wrapped command's own exit code (failure event logged). |

## Redaction

Excerpts are passed through `redact_secrets.redact()` before being written, and
the event records whether redaction changed the text (`redacted: true`). Only the
last 4000 characters of the failing stream are captured.
