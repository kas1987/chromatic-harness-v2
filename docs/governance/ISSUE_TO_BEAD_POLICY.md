# Issue → Bead Seeding & Epic Packing Policy

> **Status:** active · **Owner:** harness governance · **Tracks:** GH issues #51, #57–#65
> **Enforced by:** a two-stage pipeline — `scripts/intake_issues.py` (Stage 1, read-only)
> + `scripts/seed_issues_to_beads.py` (Stage 2, gated write) + a local idempotency ledger.

This policy closes the orphaned-issue gap: GitHub issues created from the CI/governance
hardening plan now seed **dispatchable beads** carrying explicit **eval requirements**,
grouped under **epics** for task-level execution and a summarized **E2E epic review** at close.

## 0. Two-stage architecture

The pipeline is split so the read side is robust and the write side is gated:

```
GitHub issues ──▶ Stage 1: intake_issues.py ──▶ staged_issues.jsonl / latest.json ──▶ Stage 2: seed_issues_to_beads.py ──▶ epics + child beads
                  (read-only: fetch+parse+              (staging area,                  (only writer; --apply gated;
                   validate+C-level hint)                read-only artifact)              idempotency ledger)
```

- **Stage 1 (`intake_issues.py`)** mutates nothing — it fetches open issues, parses the
  governance structure, assigns a C-level hint, validates against §1, and writes normalized
  records to `07_LOGS_AND_AUDIT/issue_intake/`. Safe to run on a hook or schedule.
- **Stage 2 (`seed_issues_to_beads.py`)** is the only component that writes beads. It reads
  the staged snapshot, groups issues into epics (§4), and creates beads behind `--apply`.
  Idempotency comes from `07_LOGS_AND_AUDIT/seed_state/issue_to_bead.json` (ext-ref → bead id).

This separation means intake can run frequently and safely, while seeding stays a deliberate,
auditable, gated action — matching the existing `intake_queue.jsonl → auto_intake.py` pattern.

---

## 1. Canonical issue/bead structure

Every governance/queue issue MUST carry these sections (the seeder parses them verbatim):

| Section | Required | Becomes (in the bead) |
|---------|----------|-----------------------|
| `## Objective` | yes | Bead one-line goal + description preamble |
| `## Scope` | yes | Bead description scope bullets |
| `## Acceptance checks` | **yes** | **Eval requirements** — the bead's definition-of-done; each `- [ ]` is a gate item |
| `## Suggested owner agent` | yes | Bead `owner-hint` + drives C-level routing |
| `bead:<slug>` reference | yes | Bead `--external-ref gh-<N>` + slug for traceability |

An issue missing `## Acceptance checks` is **rejected** by the seeder — beads without eval
requirements cannot be dispatched with precision and are not allowed.

## 2. Acceptance checks ARE the eval requirements

The `## Acceptance checks` list is copied into the bead description under a machine-readable
`## Eval requirements (definition of done)` block. A bead is only closeable when **every**
eval item has evidence (test output, artifact path, or reviewer sign-off). This is what lets
`delegate_bead.py` and human reviewers judge completion objectively rather than by vibes.

## 3. C-level routing hint (dispatch precision)

The seeder assigns a `c-level` hint from the owner agent + acceptance-check shape so
`delegate_bead.py` routes correctly (C1/C2 → local/cheap, C3 → sonnet, C4 → opus):

| Owner agent / signal | C-level | Rationale |
|----------------------|---------|-----------|
| Sentinel, Auditor (scanning, mechanical gates) | C2 | deterministic checks |
| reviewer + risk-scoring, drift detection | C3 | multi-file reasoning |
| policy-as-code, consensus design, novel synthesis | C4 | design/judgement |
| docs, config, single-file | C1 | mechanical |

The hint is advisory; `complexity_classifier` still re-scores at dispatch time.

## 4. Epic packing

Related issues are packed into a parent **epic bead** (`--type epic`), with each issue
becoming a **child task bead** (`--parent <epic-id>`). Themes:

| Epic | Issues |
|------|--------|
| **CI & Quality Hardening** | #57 security/secrets, #58 arch/docs/coverage, #60 PR size gate |
| **Governance & Review Layer** | #59 AI reviewer, #63 agent perf scoring, #64 policy-as-code, #65 review consensus |
| **Release & Ops Readiness** | #61 drift detection, #62 release readiness |
| **Queue Infrastructure** | #51 queue↔issue↔PR sync |

Child beads are dispatched and closed independently. The epic stays open until all children
close, then receives a **summarized E2E review** (§5).

## 5. E2E epic review (summarized)

When all child beads close, the epic bead gets an E2E review note aggregating:
- per-child eval-requirement pass/fail (rolled up from each child's evidence),
- the combined artifact set (preflight, scan, review outputs),
- a single ship/no-ship decision for the epic theme.

This gives task-level granularity during execution and a single governed checkpoint at the end.

## 6. Idempotency & sync

- The seeder keys on `--external-ref gh-<N>`; re-running never duplicates beads.
- Closing a child bead does **not** auto-close the GH issue (human/CI gate retained); the
  closer posts the eval evidence to the issue and closes it explicitly.
- `scripts/seed_issues_to_beads.py --dry-run` previews without writing (default-safe).

## 7. Commands

```bash
# Stage 1 — intake (read-only): fetch + parse + stage. Mutates nothing.
python scripts/intake_issues.py --print

# Stage 2 — seed (gated write). Reads the staged snapshot.
python scripts/seed_issues_to_beads.py --dry-run            # preview, no writes
python scripts/seed_issues_to_beads.py --apply              # create epics + child beads
python scripts/seed_issues_to_beads.py --refresh --apply    # run Stage 1 then seed in one shot

# Seed an explicit set under one epic
python scripts/seed_issues_to_beads.py --apply --epic "CI & Quality Hardening" --issues 57,58,60
```
