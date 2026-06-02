# Chromatic Operating Model — Vision → Reality Map

> A single reference for how the harness is meant to operate "on every level." It maps the
> target operating model to **what already exists** in this repo versus the **real gaps**,
> so we harden the gaps instead of rebuilding what we have. Authority: `CHROMATIC_TREES.md`
> remains source of truth; this organizes the operating layer around it.

## How to read this
Each capability lists: **Have** (existing system + entry point) · **Gap** (what's missing) · **Governed by** (where the rule lives). Most of the vision is already scaffolded — the work is wiring, surfacing, and closing loops, not greenfield builds.

## 1. Authoring & tracking discipline
- **Have:** `docs/playbooks/BEAD_EPIC_AUTHORING_PROTOCOL.md` + `templates/EPIC_BEAD_TEMPLATE.md` (new); bd is the single tracker; wired into `AGENT_OPERATIONS.md`.
- **Gap:** none critical — adoption + linking from every repo's README.
- **Governed by:** the protocol; serialize `bd` writes (Dolt single-writer).

## 2. Concurrency & collision control (two agents, same file)
- **Have:** a full subsystem — **lease manager** (`test_lease_manager`, P0-CC-001), **file-scope collision gate** (P0-CC-004), **double-claim guard** (P0-CC-003), **mutation manifest** (P0-CC-002), **stale-lease recovery** (P0-CC-005), **lease heartbeat** (P1-CC-006), **deadlock detector** (P1-CC-008), **autonomous collision incidents** (P1-CC-009), plus `02_RUNTIME/concurrency/github_collision.py` and the git collision PreToolUse hook. This is what stops two agents (even on the same branch) editing the same file: a claim/lease must be held; a second claimant is blocked.
- **Gap:** **awareness surface** — there's no human/agent-facing "who holds what claim right now" dashboard. Enforcement exists; visibility doesn't.
- **Governed by:** `docs/governance/COLLISION_AND_CLAIM_POLICY.md`, `04_PLAYBOOKS/PR_COLLISION_CONTROL_PLAYBOOK.md`.

## 3. Feedback loops — "comments back"
- **Have:** the **review-intake system** (just built/merged) — PR review comments / CI failures → schema-valid findings → beads (`--emit-beads`) → mission packets → evidence-gated resolution comments back to the PR. Plus `review-daemon` MCP.
- **Gap:** **wire-live** — run `--emit-beads` dispatch on real PRs and auto-post resolution comments; close the loop end-to-end on a live PR.
- **Governed by:** `08_PDRS/PDR_REVIEW_INTAKE_2026-06-01.md`, `docs/pdr/review_intake/ACCEPTANCE_PROOF.md`.

## 4. Knowledge flywheel — error logs → learning → accumulation
- **Have:** `ao` knowledge ops + `bd remember`; **observability v2.1** (events, incidents, lifecycle, reports); `toolchain-family:harvest` (cross-rig consolidation); `/post-mortem` learnings; auto-memory.
- **Gap:** **error-log → flywheel wiring** — ensure failed CI / harness errors auto-generate learning candidates, and the harvest cadence runs (not ad hoc).
- **Governed by:** observability PDR; harvest skill.

## 5. Multi-repo convergence & the Chromatic wiki
- **Have:** **federation** (`~/.claude/governance/auto-mode-scope.yaml`, repo-role registry PDR-FED-001); **wiki promotion** (`docs/WIKI_REPO_AND_PROMOTION.md`, `sync_wiki_mirror.py`, `promote_to_wiki.py`).
- **Gap:** a **convergence cadence** — when/what each repo in the chromatic family promotes to the shared wiki; dedupe across repos.
- **Governed by:** federation scope + wiki promotion docs.

## 6. Skill hot-swap & token debt
- **Have:** `skills-family.ps1 [core|pipeline|trust|toolchain|all]` toggles skill families; plugin families (pipeline/trust/toolchain) load on demand; `audit_mcp_context.py`, `agent_token_audit.py`.
- **Gap:** **per-task skill profiles** (finer than family-level) + a loaded-skill **token-cost audit** so precontext debt is measured and minimized per task type.
- **Governed by:** `~/.claude/governance/subagent-token-efficiency.md`.

## 7. Model routing — local vs cloud, which model/IDE/CLI
- **Have:** **model-router** (C1-C4 tiers: C1/C2 mechanical→haiku/local, C3→sonnet, C4→opus), `test_complexity_and_routing`, router auto-path/fallback, `model-router.sh` advisory hook, `~/.claude/governance/model-routing-for-subagents.md` (local-OL vs cloud vs no-LLM matrix).
- **Gap:** an explicit **cloud-vs-local decision policy** doc (when Llama/Gemini/GPT/cloud each win) and making the router's advice **enforced**, not just advisory.
- **Governed by:** model-routing governance docs.

## 8. Autonomous long-running loops
- **Have:** `/loop`, `/crank` (hands-free epic execution), auto-mode (T1-T3 never blocked), `CONTINUOUS_EXECUTION_SOP`, budget forecasting in session boot.
- **Gap:** a **flag taxonomy** for "how autonomous" (e.g. scope/T-level/budget ceilings per loop) and **token-budget guards** that pause a long loop at a spend threshold.
- **Governed by:** `docs/governance/CONTINUOUS_EXECUTION_SOP.md`, global auto-mode scope.

## 9. Root hygiene & anti-inflation
- **Have:** numbered taxonomy (`00_`–`12_`), `ARTIFACT_MANIFEST.json`, root-artifact hygiene logs.
- **Gap:** root has scratch clutter (`_v3_bead_map.json`, `_v3_beads.ps1`, `hook_audit.json`, loose `INTEGRATION_TEST.ts`); no **root-hygiene gate** to prevent new clutter.
- **Governed by:** (proposed) a pre-commit root-allowlist check.

## 10. Playbook coverage — "operate on every level"
- **Have:** `04_PLAYBOOKS/` + `docs/playbooks/`.
- **Gap:** a **coverage audit** — one playbook per operating level (author, dispatch, collision, review, learn, route, loop, promote) with no holes; index them.

## Prioritization
Threads 2, 7, 8 are **enforcement/visibility gaps on systems that already work** (highest leverage, lowest build cost). Threads 3, 4, 5 are **loop-closure** (real value, moderate cost). Threads 6, 9, 10 are **hygiene/efficiency** (cheap, compounding). This map should be decomposed into an "Operating-Model Hardening" epic via the authoring protocol — dogfooding the system it governs.
