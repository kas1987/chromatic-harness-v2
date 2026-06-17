# SWOT — Security cluster

**Audit date:** 2026-06-16
**Analyst:** automated SWOT pass
**Base path:** `07_LOGS_AND_AUDIT/security/`

---

## Folder inventory

| Item | Files | Size (KB) | Newest mtime | Has latest.json | Schema summary | Fresh/Stale |
|---|---|---|---|---|---|---|
| `security/` (timestamped snapshots) | 283 | ~75.7 KB | 2026-06-16 11:18 | Yes (343 B) | `{secrets, dependencies, high_severity_total, passed, timestamp}` | **Fresh** (latest today) |
| `security/latest.json` | 1 | 0.34 KB | 2026-06-16 11:18 | — | Same as above; dep status=`ok`, scope=`requirements.txt` | Fresh |
| `security/service_auth_latest.json` | 1 | 2.25 KB | 2026-06-01 10:26 | — | `{schema_version, timestamp, overall_risk, services_running, critical_count, findings[]}` | **Stale** (15 days old) |
| `security/log_integrity_latest.json` | 1 | 0.08 KB | 2026-06-04 17:48 | — | `{schema_version, built_at, targets: {}}` | **Stale** (12 days old); targets is empty `{}` |

**Total: 286 files, ~77 KB (0.08 MB)**

Date range of timestamped snapshots: 2026-06-01T13:15Z – 2026-06-16T15:17Z (16 days)

Snapshot distribution by dependency scan status (283 timestamped files):
- `dependencies.status = "skipped"`: **282 files** (99.6%)
- `dependencies.status = "ok"` with scope `requirements.txt`: **1 file** (today's scan only; `20260616T151724Z.json`)

---

## Strengths

1. **Gate is wired and active.** `scripts/security_scan.py` is called by both `ci.yml` (secret scan, `--no-deps`) and `harness-observability-check.yml` (full scan including `pip-audit`). Results feed `session_closeout.py` and `scripts/release_readiness.py`. The gate exits 1 on any high-severity finding.

2. **Secrets scanner is well-designed.** Five regex patterns mirror the pre-commit hook (`SECRET_PATTERN`), ensuring local and CI scanners are consistent. The `pragma: allowlist secret` suppression mechanism is present. Scanner is scoped to git-tracked files only, skipping `07_LOGS_AND_AUDIT/` (avoids self-referential hits). A dedicated `SKIP_DIRS` + `SKIP_SUFFIXES` allowlist is maintained.

3. **Schema is stable and consistent.** All 283 timestamped snapshots share the same top-level key set. `latest.json` is always a copy of the most recent scan. `summarize()` in `security_scan.py` reads `latest.json` rather than re-scanning (fast closeout).

4. **Test coverage exists.** `tests/test_security_scan.py`, `tests/test_secret_scan_gate.py`, and e2e runner reference the scanner. The scanner is also verified in `test_observability_ci_workflow.py`.

5. **`service_auth_latest.json` provides local-service port-binding audit.** Covers Ollama, Neo4j, ChromaDB, ComfyUI with `secure_default` flags and concrete guidance.

6. **Today's `latest.json` shows genuine dep scan ran.** Dependencies status is `ok` with scope `requirements.txt` and zero vulnerabilities — the current posture is not just "passed by skipping."

---

## Weaknesses

1. **282 of 283 historical snapshots record dependency scanning as `"skipped"`.** The scanner was invoked with `--no-deps` in every local/hook context (e2e runner: `run-all-e2e.py` explicitly passes `--no-deps`; `ci.yml` main gate also uses `--no-deps`). Only the `harness-observability-check.yml` CI workflow installs `pip-audit` and runs the full scan. This means dependency scanning has been structurally absent from all local developer runs and main CI gates throughout the project's history.

2. **Unbounded snapshot accumulation — no rotation/retention policy.** `write_artifact()` in `security_scan.py` creates a new timestamped JSON on every invocation with no pruning logic. 283 files accumulated in 16 days (~18/day on busy days: up to 7 scans/hour on 2026-06-03). At this rate the directory grows indefinitely. No `.gitignore` exclusion or cleanup script exists.

3. **`log_integrity_latest.json` has `targets: {}`** — the log integrity scan produced an empty result and has not been refreshed in 12 days. This artifact purports to validate log integrity but contains no data, providing false assurance.

4. **`service_auth_latest.json` is 15 days stale.** Local service posture (Ollama, Neo4j, ChromaDB) is only snapshotted once; no refresh mechanism exists. If Ollama is reconfigured or a new service is added, this artifact becomes misleading.

5. **Schema divergence between artifact types.** `latest.json`, `service_auth_latest.json`, and `log_integrity_latest.json` have completely different schemas with no shared `schema_version` field in `latest.json`. Cross-cluster readers cannot verify compatibility programmatically.

6. **`20260601T131504Z.json` through to today's sole `ok` scan**: 282 files with `dep status=skipped` that all record `passed: true` — these are technically truthful (high_severity_total=0 because skipped contributes 0) but misleading. The gate passes without actually testing dependencies.

---

## Opportunities

1. **Enforce `pip-audit` in `ci.yml` main gate.** The `harness-observability-check.yml` already installs and runs it correctly. Adding `pip install pip-audit` + running without `--no-deps` in `ci.yml` would close the dependency gap for every PR. The `requirements.txt` scoping design already exists and is correct.

2. **Add retention/rotation to `write_artifact()`.** A 30-scan or 30-day cap (keep `latest.json` + last N timestamped copies) would reduce the directory from unbounded growth to a fixed ceiling. Could be a 5-line addition to `write_artifact()`.

3. **Refresh `service_auth_latest.json` on session start.** Wire a lightweight service port scan into the `SessionStart` hook or `pre_session` workflow; it is currently a one-time artifact from 2026-06-01.

4. **Populate or remove `log_integrity_latest.json`.** Either implement the log-integrity scanner (populate `targets`) or remove the empty stub artifact. An empty `targets: {}` is worse than no file — it suggests coverage that does not exist.

5. **Add `schema_version` to `latest.json`.** Aligns with `service_auth_latest.json` (already has `schema_version: 1`) and enables future consumers to reject incompatible formats.

6. **Consolidate the three "latest" artifact types under a single `security/latest.json` umbrella.** A merged artifact with sub-objects for `secrets_scan`, `service_auth`, and `log_integrity` would give a single truth file for `release_readiness.py` to consume.

---

## Threats

1. **Structural false-positive gate pass.** CI `ci.yml` runs `security_scan.py --no-deps`, which always records `dependencies.status = "skipped"` and contributes 0 to `high_severity_total`. If a vulnerability is introduced into `requirements.txt`, the main CI gate will not catch it — only the weekly/manual `harness-observability-check.yml` run would. A dependency with a known CVE could ship.

2. **File bloat becomes a repo health issue.** At 18 scans/day the directory doubles in file count roughly every two weeks. In a git-tracked repo this inflates `.git` pack sizes and slows `git status`, `git add`, and `git log` operations. The 283 files are currently only ~77 KB, so not a storage crisis today, but the trajectory is unbounded.

3. **`log_integrity_latest.json` empty `targets: {}`** creates audit theater. Any process reading this file to confirm log integrity has been validated will receive a false "validated" signal.

4. **`service_auth_latest.json` freshness decay.** A stale service-auth snapshot that predates any config changes (e.g., Ollama host binding change, addition of a new local service) could mask a real network exposure.

5. **Secret scan excludes `07_LOGS_AND_AUDIT/`.** This is intentional (avoids self-match), but it means any secrets accidentally written into an audit log file (e.g., a token captured in a scan output) would not be caught. The `service_auth_latest.json` already embeds service descriptions; if a future scanner captures env vars or connection strings it would be invisible to the secrets gate.

---

## Cleanup Recommendations

### P0 — Fix structural dep-scan gap (security posture at risk)

**Action:** In `.github/workflows/ci.yml`, add `pip install pip-audit` before the `security_scan.py` step and remove `--no-deps` from that step.

```yaml
- name: Install dependency scanner
  run: python -m pip install pip-audit
- name: Governance gate — secret + dependency scan (blocking)
  run: python scripts/security_scan.py
```

**Rationale:** 282 of 283 historical scans skipped dependency auditing. `latest.json` has only today shown `dep status=ok`. The main CI gate (ci.yml) has never blocked on a dependency CVE. This is the highest-severity finding.

**Also:** Update `tests/run-all-e2e.py` to remove `--no-deps` from Gate 0.5 (or add a separate full-dep scan step). The e2e runner is a developer-facing gate that also silently skips dep scanning.

---

### P0 — Fix `log_integrity_latest.json` empty artifact

**Action:** Either implement the log-integrity scanner to populate `targets`, or delete the file. An empty `targets: {}` provides false coverage assurance.

**Rationale:** Any consuming process (e.g., `release_readiness.py`) that reads this file gets a structurally valid JSON with no substantive data, making it appear log integrity has been checked when it has not.

---

### P1 — Add retention/rotation to `write_artifact()`

**Action:** In `scripts/security_scan.py` `write_artifact()`, add pruning after writing:

```python
# Keep the 50 most recent timestamped snapshots
snapshots = sorted(ARTIFACT_DIR.glob("2026*.json"))
for old in snapshots[:-50]:
    old.unlink(missing_ok=True)
```

**Rationale:** 283 files in 16 days with no ceiling. A 50-file cap retains ~3 days of dense scanning history while eliminating unbounded growth. `latest.json`, `service_auth_latest.json`, and `log_integrity_latest.json` are named files and would not be affected by the glob pattern.

---

### P1 — Refresh `service_auth_latest.json` regularly

**Action:** Wire the service-auth scanner into the `pre_session` hook or as a step in `harness-observability-check.yml`. The current file is from 2026-06-01.

**Rationale:** A 15-day-old port-binding snapshot is not a security control — it is a historical record. If Ollama or another service has been reconfigured since then, the snapshot gives false confidence.

---

### P2 — Add `schema_version` to `latest.json` / main security artifact

**Action:** In `write_artifact()`, add `"schema_version": 1` to the payload. Update `summarize()` to verify it.

**Rationale:** Aligns with `service_auth_latest.json` schema versioning. Enables future consumers to detect format changes.

---

### P2 — Consider `.gitignore` for timestamped security snapshots

**Action:** Add `07_LOGS_AND_AUDIT/security/2026*.json` (or a dated prefix pattern) to `.gitignore` and commit only `latest.json` + the three named `*_latest.json` files.

**Rationale:** 283 small JSON files in a git-tracked directory inflate pack size over time. The timestamped snapshots are operational artifacts (useful for local debugging) but have low long-term audit value vs. the always-current `latest.json`.

---

## Cross-cluster notes

- `scripts/release_readiness.py` reads `security/latest.json` directly — fixing the dep-scan gap in CI will immediately propagate to release-readiness scoring without any additional changes.
- The `service_auth_latest.json` schema pattern (with `schema_version`, `overall_risk`, `findings[]`) is a better template than the flat `latest.json` structure. Consider adopting it as the unified security artifact schema.
- `07_LOGS_AND_AUDIT/collision/` and other clusters may have similar unbounded-growth patterns — the retention fix should be applied uniformly via a shared utility rather than per-scanner.
- The `SKIP_DIRS` exclusion of `07_LOGS_AND_AUDIT` from secret scanning is correct but should be documented in `docs/security/SECURITY_GATES.md` (currently undocumented) so future contributors do not incorrectly assume audit logs are scanned.
