---
id: plan-2026-06-02-chv2-hardening
type: plan
date: 2026-06-02
source: "C:/Users/kas41/Downloads/_hardening_extract/chromatic_harness_v2_hardening_pdr/docs/pdr/PDR_CHROMATIC_HARNESS_V2_HARDENING.md"
---

# Plan: Chromatic Harness v2 Hardening (CHV2-HARDEN-001)

## Context
Harden `chromatic-harness-v2` from a visual-control scaffold into a validated, manifest-driven
installable package. A drop-in package ships the target implementations (validators, manifest,
expanded registry, n8n contract, CI gate); this epic lands the hardened versions and PROVES the
10 PDR acceptance criteria. Five controls: visual-control-plane validation, manifest-driven
install safety, CI validation gate, operational registry expansion, n8n boundary governance.

Authority rule preserved: `CHROMATIC_TREES.md` remains source of truth; this package extends
validation/packaging/safety only.

## Files to Modify

| File | Change |
|------|--------|
| `scripts/validate_visual_control_plane.py` | **NEW** — registry/schema/adapter/regeneration validator |
| `scripts/validate_install_manifest.py` | **NEW** — manifest path + required-file validator |
| `install_manifest.json` | **NEW** — explicit installer allowlist |
| `scripts/install_visual_control_plane.py` | Replace recursive-by-exclusion copy with manifest-driven + `--dry-run` |
| `docs/contracts/INSTALLER_SAFETY_CONTRACT.md` | **NEW** — installer safety contract |
| `visual_node_registry.json` | Expand 10 diagram nodes → operational (owner, source_of_truth, inputs, outputs, required_checks, failure_mode) |
| `schemas/visual_node.schema.json` | Tighten to require operational fields |
| `.github/workflows/visual-control-plane-validate.yml` | **NEW** — PR validation gate |
| `docs/contracts/N8N_BOUNDARY_CONTRACT.md` | **NEW** — n8n authority boundary |
| `docs/playbooks/HARDENING_PLAYBOOK.md` | **NEW** — operating playbook |
| `tests/test_visual_control_plane.py` | **NEW** — validator unit tests (dup IDs, broken edges, adapter drift) |

## Boundaries
**Always:** preserve `CHROMATIC_TREES.md` as source of truth; manifest allowlist + `--dry-run` for installer; every validator failure mode has a test; wire new suites into `run-all-e2e.py`.
**Ask First:** none (package is pre-specified; autonomous).
**Never:** rewrite the whole v2 repo; replace `CHROMATIC_TREES.md`; make n8n the governance brain; grant agents broad cross-repo mutation; build a web dashboard this sprint.

## Baseline Audit

| Metric | Command | Result |
|--------|---------|--------|
| Required artifacts absent | `for f in <12 required>; do test -e $f; done` | 6 absent (manifest, both validators, CI workflow, n8n contract, playbook), 6 exist |
| Existing installer is scaffold-grade | `grep -nE "manifest\|allowlist\|--dry-run\|copytree" scripts/install_visual_control_plane.py` | 0 matches — recursive-by-exclusion confirmed; differs from package |
| Registry is diagram-only | `grep -oE "owner\|source_of_truth\|inputs\|outputs\|required_checks\|failure_mode" visual_node_registry.json` | 0 of 6 operational fields present (10 nodes) |
| Schema strictness | `grep -l "additionalProperties.*false" schemas/*.json` | none strict (no ordering hazard) |

## Issues

### Issue 1 (CHV2-001): Add visual control plane validator
**Dependencies:** None
**Owner:** Auditor · **Priority:** 95
**Description:** Add `scripts/validate_visual_control_plane.py` (from package) verifying required files, registry validity (fail on **duplicate node IDs** and **edges referencing missing nodes**), schema validity, Mermaid regeneration freshness, and adapter source-of-truth deference. Add `tests/test_visual_control_plane.py` covering each failure mode (use `tests/fixtures/bad_duplicate_registry.json` from the package).
**Acceptance:** `python scripts/validate_visual_control_plane.py --root .` passes on good input, fails on dup IDs / broken edges / adapter drift.
```validation
{"files_exist": ["scripts/validate_visual_control_plane.py", "tests/test_visual_control_plane.py"], "command": "python scripts/validate_visual_control_plane.py --root ."}
```

### Issue 2 (CHV2-002): Manifest-driven installer + manifest validator
**Dependencies:** None
**Owner:** Sentinel · **Priority:** 92
**Description:** Add `install_manifest.json` (explicit allowlist), replace the recursive-by-exclusion `scripts/install_visual_control_plane.py` with manifest-driven copy supporting `--dry-run` and backup. Add `scripts/validate_install_manifest.py` verifying manifest paths + required package files. Add `docs/contracts/INSTALLER_SAFETY_CONTRACT.md`.
**Acceptance:** installer copies only manifest-listed files; `--dry-run` works; manifest validator passes.
```validation
{"files_exist": ["install_manifest.json", "scripts/validate_install_manifest.py", "docs/contracts/INSTALLER_SAFETY_CONTRACT.md"], "command": "python scripts/validate_install_manifest.py --root . && python scripts/install_visual_control_plane.py --target /tmp/chv2-install-test --dry-run"}
```

### Issue 3 (CHV2-003): Expand registry into operational control registry
**Dependencies:** Issue 1 (validator must exist to validate the expanded registry; shares schema)
**Owner:** Archivist · **Priority:** 88
**Description:** Expand `visual_node_registry.json` (10 nodes) so each node has `owner`, `source_of_truth`, `inputs`, `outputs`, `required_checks`, `failure_mode`. Tighten `schemas/visual_node.schema.json` to require these. Registry must validate through the CHV2-001 validator.
**Acceptance:** every node has the 6 operational fields; registry validates.
```validation
{"files_exist": ["visual_node_registry.json", "schemas/visual_node.schema.json"], "content_check": {"file": "visual_node_registry.json", "pattern": "source_of_truth"}, "command": "python scripts/validate_visual_control_plane.py --root ."}
```

### Issue 4 (CHV2-004): Add GitHub Actions validation workflow
**Dependencies:** Issue 1, Issue 2 (workflow invokes both validators)
**Owner:** Sentinel · **Priority:** 84
**Description:** Add `.github/workflows/visual-control-plane-validate.yml` that validates registry + manifest, regenerates Mermaid, and **fails on stale generated docs**, on PRs. Use `actions/checkout@v5` + `actions/setup-python@v6` (Node 24). Wire into the PR gate.
**Acceptance:** workflow runs on PRs; validates registry+manifest; fails on stale Mermaid.
```validation
{"files_exist": [".github/workflows/visual-control-plane-validate.yml"], "content_check": {"file": ".github/workflows/visual-control-plane-validate.yml", "pattern": "validate_visual_control_plane.py"}}
```

### Issue 5 (CHV2-005): Create n8n boundary contract + hardening playbook
**Dependencies:** None
**Owner:** Auditor · **Priority:** 76
**Description:** Add `docs/contracts/N8N_BOUNDARY_CONTRACT.md` defining allowed vs forbidden n8n actions and linking queue updates to confidence-gate requirements (n8n remains a workflow surface, not governance authority). Add `docs/playbooks/HARDENING_PLAYBOOK.md`.
**Acceptance:** contract enumerates allowed + forbidden actions and references the confidence gate.
```validation
{"files_exist": ["docs/contracts/N8N_BOUNDARY_CONTRACT.md", "docs/playbooks/HARDENING_PLAYBOOK.md"], "content_check": {"file": "docs/contracts/N8N_BOUNDARY_CONTRACT.md", "pattern": "[Ff]orbidden"}}
```

## Conformance Checks

| Issue | Check Type | Check |
|-------|-----------|-------|
| 1 | command | `python scripts/validate_visual_control_plane.py --root .` |
| 2 | command | `python scripts/validate_install_manifest.py --root . && install … --dry-run` |
| 3 | content_check | `visual_node_registry.json` contains `source_of_truth` |
| 4 | content_check | workflow references `validate_visual_control_plane.py` |
| 5 | content_check | n8n contract contains `forbidden` |

## File-Conflict Matrix

| File | Issues |
|------|--------|
| `scripts/validate_visual_control_plane.py` | Issue 1 |
| `scripts/install_visual_control_plane.py`, `install_manifest.json`, `scripts/validate_install_manifest.py` | Issue 2 |
| `visual_node_registry.json`, `schemas/visual_node.schema.json` | Issue 3 |
| `.github/workflows/visual-control-plane-validate.yml` | Issue 4 |
| `docs/contracts/N8N_BOUNDARY_CONTRACT.md`, `docs/playbooks/HARDENING_PLAYBOOK.md` | Issue 5 |

No same-file collisions within a wave.

## Cross-Wave Shared Files

| File | Wave 1 | Wave 2 | Mitigation |
|------|--------|--------|------------|
| `schemas/visual_node.schema.json` | read by Issue 1 | modified by Issue 3 | Issue 3 depends on Issue 1; Wave 2 worktree branches from post-Wave-1 SHA |

## Execution Order

**Wave 1** (parallel): Issue 1 (CHV2-001), Issue 2 (CHV2-002), Issue 5 (CHV2-005)
**Wave 2** (after Wave 1): Issue 3 (CHV2-003 ← 1), Issue 4 (CHV2-004 ← 1,2)

## Planning Rules Compliance

| Rule | Status | Justification |
|------|--------|---------------|
| PR-001: Mechanical Enforcement | PASS | Every control has a runnable validator/CI gate; no honor-system steps. |
| PR-002: External Validation | PASS | CI workflow (Issue 4) validates independently of the author; acceptance is command-based. |
| PR-003: Feedback Loops | PASS | Validators consumed by CI gate; registry consumed by generator; manifest consumed by installer — each output has a named consumer. |
| PR-004: Separation Over Layering | PASS | Installer/validators/registry/contract are separate files with explicit contracts; n8n boundary is an explicit contract. |
| PR-005: Process Gates First | PASS | Validators + manifest contract (process gates) precede the CI tool change (Wave 2). |
| PR-006: Cross-Layer Consistency | PASS | Registry schema (Issue 3) and validator (Issue 1) agree on the 6 operational fields; CI uses the same validators. |
| PR-007: Phased Rollout | PASS | Wave 1 lands validators/installer/contract; Wave 2 wires CI + expands registry after validators exist. |

Unchecked rules: 0

## Verification
1. `python scripts/validate_visual_control_plane.py --root .`
2. `python scripts/validate_install_manifest.py --root . && python scripts/install_visual_control_plane.py --target /tmp/chv2-install-test --dry-run`
3. `python -m pytest tests/test_visual_control_plane.py -q`
4. Full gate: `python tests/run-all-e2e.py`

## Next Steps
- `/pre-mortem` to validate plan, then `/crank` for autonomous execution (or `/implement CHV2-001`).
