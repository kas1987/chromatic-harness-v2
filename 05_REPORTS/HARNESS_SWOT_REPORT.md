# Harness SWOT Analysis Report

Generated: 2026-06-21T18:31:31Z  
Harness root: `E:\.02_chromatic-harness-v2`

---

## S — Strengths

### CI/CD Coverage
- Workflow files present: **14**
  - `auto-label.yml`
  - `auto-update-branches.yml`
  - `branch-governance-weekly.yml`
  - `ci-governance-weekly.yml`
  - `ci.yml`
  - `harness-daily-audit.yml`
  - `harness-governance.yml`
  - `harness-observability-check.yml`
  - `harness-review-intake-check.yml`
  - `merge-gate.yml`
  - `repo-settings.yml`
  - `review-intake.yml`
  - `validate-command-prompt-system.yml`
  - `visual-control-plane.yml`

### Governance Documentation
  - **[PASS]** `CLAUDE.md`
  - **[PASS]** `AGENTS.md`
  - **[PASS]** `README.md`
  - **[PASS]** `pyproject.toml`
  - **[PASS]** `pytest.ini`
  - **[PASS]** `DEPLOYMENT_GUIDE.md`
  - **[PASS]** `GOVERNANCE_AND_ROUTING_ARCHITECTURE.md`

### Script Validation Coverage
- Scripts with test counterparts: **97**
- Scripts without tests: **139**
- Test files total: **312**

### Git Health
- Current branch: `feature/harness-finalization-2026-06-20`
- Worktree clean: **[FAIL]**
- Up to date with remote: **[PASS]**

---

## W — Weaknesses

### Scripts Without Test Coverage
- Count: **139**

<details><summary>View uncovered scripts (up to 30)</summary>

  - `__init__.py`
  - `__init__.py`
  - `active_sessions.py`
  - `analyze_auto_turn_observations.py`
  - `append_session_telemetry.py`
  - `audit_ide_parity.py`
  - `audit_instruction_drift.py`
  - `baseline_snapshot.py`
  - `bd_closed_window.py`
  - `bd_ready_by_lane.py`
  - `bdbranch_slug.py`
  - `bead_hygiene_apply_remediation.py`
  - `bead_hygiene_audit.py`
  - `bead_hygiene_autoloop.py`
  - `bead_hygiene_remediation_commands.py`
  - `bootstrap_observability.py`
  - `branch_governance_audit.py`
  - `branch_governance_autonomy.py`
  - `branch_governance_enforce.py`
  - `cache_hit_rate.py`
  - `candidate_count.py`
  - `canon_count.py`
  - `capture_count.py`
  - `capture_external.py`
  - `cat_intake_bridge.py`
  - `check_beads_dolt_health.py`
  - `check_dirty_state.py`
  - `check_rate_limit.py`
  - `check_wiki_harness_sync.py`
  - `chromatic_mcp_server.py`

</details>

### .pyc / Cache Hygiene
- `*.pyc` in .gitignore: **[PASS]**
- Tracked `.pyc` files: **0**

### Empty Directories
- Count: **15**
  - `.agents\intake/`
  - `.beads\backup\oldgen/`
  - `.beads\embeddeddolt\chromatic_harness_v2\.dolt\git-remote-cache\cca1faf81f34e57d939cf365ac5c69e61cc8f9987bb15efa0aea4098493b5614\repo.git\branches/`
  - `.beads\embeddeddolt\chromatic_harness_v2\.dolt\git-remote-cache\cca1faf81f34e57d939cf365ac5c69e61cc8f9987bb15efa0aea4098493b5614\repo.git\objects\info/`
  - `.beads\embeddeddolt\chromatic_harness_v2\.dolt\git-remote-cache\cca1faf81f34e57d939cf365ac5c69e61cc8f9987bb15efa0aea4098493b5614\repo.git\refs\dolt/`
  - `.beads\embeddeddolt\chromatic_harness_v2\.dolt\git-remote-cache\cca1faf81f34e57d939cf365ac5c69e61cc8f9987bb15efa0aea4098493b5614\repo.git\refs\tags/`
  - `.beads\embeddeddolt\chromatic_harness_v2\.dolt\noms\oldgen/`
  - `.git\modules\02_RUNTIME\runtime-engines\roach-pi\objects\info/`
  - `.git\refs\heads\docs/`
  - `.git\refs\heads\fix/`
  - _(and 5 more)_

### Stale Branches (merged into main, not deleted)
- Count: **0**

### Documentation Staleness (>90 days)
- Old docs count: **0**

---

## O — Opportunities

### Auto-Healing Candidates (TODO/FIXME/HACK markers)
- Scripts with actionable markers: **6**

| Script | Marker Count |
|--------|-------------|
| `sla_metrics_collector.py` | 5 |
| `ai_review_gate.py` | 4 |
| `harness_swot.py` | 3 |
| `audit_instruction_drift.py` | 1 |
| `consensus_workflow.py` | 1 |
| `validate_pr_governance.py` | 1 |

### Test Coverage Improvement
- Current script coverage: **41.1%**
- Potential coverage (if all gaps filled): **100.0%**

Top 10 highest-value test gap targets (by file size):
  - `daily_harness_audit.py`
  - `harness_health_snapshot.py`
  - `token_governance_closed_loop.py`
  - `generate_pre_session_inventory.py`
  - `swot_autonomy_loop.py`
  - `claude_delegate_gate.py`
  - `usage_calibrate.py`
  - `llm_governance_intelligence.py`
  - `codegraph_effectiveness_scorecard.py`
  - `seed_issues_to_beads.py`

### Branch Simplification
- Remote branches total: **7**
- Non-main remote branches (merge/prune candidates): **6**
  - `origin/__dolt_remote_info__`
  - `origin/docs/harness-v2-assessment-synthesis`
  - `origin/feat/command-center-p1-p2`
  - `origin/feat/review-intake-loop-metrics`
  - `origin/feature/harness-finalization-2026-06-20`
  - `origin/session/chromatic-harness-v2-initial`

---

## T — Threats

### Large Tracked Files (>5 MB)
- Count: **0**

### Potential Secret Exposure
- Files with secret-pattern hits: **20**

  - `.github\workflows\auto-label.yml`
    - line 17: private-key: ${{ secrets.APP_PRIVATE_KEY }}  # pragma: allowlist secret
  - `.github\workflows\auto-update-branches.yml`
    - line 36: private-key: ${{ secrets.APP_PRIVATE_KEY }}  # pragma: allowlist secret
  - `.github\workflows\ci.yml`
    - line 25: private-key: ${{ secrets.APP_PRIVATE_KEY }}  # pragma: allowlist secret
  - `.github\workflows\repo-settings.yml`
    - line 28: private-key: ${{ secrets.APP_PRIVATE_KEY }}  # pragma: allowlist secret
  - `02_RUNTIME\api\main.py`
    - line 201: token = create_access_token(user_id=row[0], role=row[2])  # pragma: allowlist se
  - `02_RUNTIME\concurrency\session_lock.py`
    - line 183: owner_token = acquire_lock(
  - `02_RUNTIME\gen\src\core\startup-validation.ts`
    - line 14: const genToken = process.env.GEN_TOKEN; // pragma: allowlist secret
  - `02_RUNTIME\gen\src\middleware\auth.ts`
    - line 7: const expectedToken = process.env.GEN_TOKEN; // pragma: allowlist secret
    - line 23: const token = req.headers.authorization?.replace("Bearer ", ""); // pragma: allo
  - `02_RUNTIME\router\adapters\openhuman_adapter.py`
    - line 51: token = os.environ.get(self.cfg.get("env_key", "OPENHUMAN_BEARER_TOKEN"), "")
  - `05_REPORTS\HARNESS_SWOT_REPORT.md`
    - line 165: - line 17: private-key: ${{ secrets.APP_PRIVATE_KEY }}  # pragma: allowlist secr
    - line 167: - line 36: private-key: ${{ secrets.APP_PRIVATE_KEY }}  # pragma: allowlist secr
    - line 169: - line 25: private-key: ${{ secrets.APP_PRIVATE_KEY }}  # pragma: allowlist secr
  - `12_HANDOFFS\SESSION_2026-05-28_FINAL.md`
    - line 84: GITHUB_TOKEN=ghp_REDACTED_ROTATED_2026-06-21...
    - line 89: PRISM_GEN_TOKEN=dev-local-token-2026
  - `docs\ops\OBSERVABILITY_IMPLEMENTATION_GUIDE.md`
    - line 284: pagerduty_token = os.environ.get("PAGERDUTY_INTEGRATION_KEY")
  - `scripts\ci_runtime_budget_report.py`
    - line 158: token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")  # pragma: 
  - `scripts\harness_health_snapshot.py`
    - line 253: token = _read_json(TOKEN_GOV)  # pragma: allowlist secret
  - `scripts\session_closeout.py`
    - line 1488: token = line.split()[0] if line else ""

### Syntax Errors in Python Files
- Files with syntax errors: **0**
  - _No syntax errors detected._

### Missing Required Files
  - _All required files present._

---

## Summary Score

| Quadrant | Key Metric |
|----------|-----------|
| Strengths | 14 CI workflows · 97 validated scripts · 312 test files |
| Weaknesses | 139 untested scripts · 0 stale branches · 15 empty dirs |
| Opportunities | 6 auto-heal targets · 41.1% → 100% coverage potential |
| Threats | 0 large files · 20 secret-pattern files · 0 syntax errors |

_Report generated by `scripts/harness_swot.py` at 2026-06-21T18:31:31Z_