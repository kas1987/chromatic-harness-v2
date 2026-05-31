# Root Artifact Hygiene Policy

## Purpose

Keep repository root readable and predictable by moving known operational
artifacts out of root and deleting disposable runtime clutter.

## Scope

This policy applies only to root-level artifact clutter, not source code,
configs, or canonical project docs.

## Automation Command

Dry-run (default):

```bash
python scripts/root_artifact_hygiene.py
```

Apply changes:

```bash
python scripts/root_artifact_hygiene.py --write
```

Report output:

```text
07_LOGS_AND_AUDIT/root_artifacts/latest_root_artifact_hygiene.json
```

## Governance Rules

1. Default mode must remain dry-run.
2. Write mode must only affect explicit allowlisted artifact names/patterns.
3. Tracked temp artifacts should be moved to
   `07_LOGS_AND_AUDIT/root_artifacts/`, not deleted.
4. Disposable ignored runtime outputs may be deleted.
5. Any expansion of the allowlist requires a PR note with rationale and risk.
6. Never include core root anchors in cleanup scope:
   `README.md`, `AGENTS.md`, `AGENT_OPERATIONS.md`, `CLAUDE.md`,
   `requirements.txt`, `pytest.ini`, `mypy.ini`, `.coveragerc`.

## Current Managed Artifact Classes

Moved to `07_LOGS_AND_AUDIT/root_artifacts/`:

- `.tmp_*`
- `server_stderr.txt`
- `server_stdout.txt`
- `__bh_autoloop_ec.txt`
- `__bh_autoloop_out.txt`

Deleted from root when present:

- `.coverage`
- `check_files.log`
- `prepush2.log`
- `prepush_sim.log`
- `__bh_run.log`
- malformed leftovers: `0)`, `0))`, `,m.get(wiki_dest)) for m in matches[`
- temporary ingest dirs: `.tmp_ingest`, `.tmp_pre_session_pack`

## Operational Cadence

- Run dry-run during daily bootstrap.
- Run write mode before PR creation or at session closeout.
- Review the generated JSON report in audit logs for unexpected actions.
