# Chromatic Harness Observability + Error Intelligence v2.1

This package turns Harness errors into durable operational intelligence.

## What v2.1 Adds

- Active file claim/release controls
- Command wrapper for terminal/build/test failures
- Event routing to incident, collision, and queue artifacts
- Stronger event schema validation
- Git state snapshots
- Secret scanning
- VS Code / Cursor task integration
- Git hook templates
- GitHub Actions workflow
- Observability reports
- Remediation queue
- Clean manifest and package hygiene

## Quick Start

```bash
python scripts/bootstrap_observability.py --repo-root .
python scripts/validate_event_schema.py --log 00_META/observability/ERROR_LOG.jsonl
python scripts/claim_files.py --writer codex --session demo --task TEST --files README.md
python scripts/release_files.py --session demo --all-for-session
```

## Run Commands Through the Harness

```bash
python scripts/harness_run.py --route -- npm run build
```

## Main PDR

See `00_META/observability/PDR_CHROMATIC_HARNESS_OBSERVABILITY_V2_1.md`.
