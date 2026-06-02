# Agent Operations — Mandatory for All Harness Agents

> **Applies to:** Claude, Pi, Codex, Cursor agents, and every runtime in Chromatic Harness v2.  
> **If you skip this, you will break governance, miss MCP/CRG changes, or strand work.**

This is the single entry point for *operational behavior*. Sub-docs go deeper; this page is the checklist nothing is allowed to skip.

**Repo structure & "which file do I use?":** [CHROMATIC_TREES.md](CHROMATIC_TREES.md) — the structure source-of-truth + the operation→file map (create epic/bead/roadmap/PDR/retro). This page is the *checklist*; that file is the *map*.

**Rules map (all layers):** [docs/RULES_INVENTORY.md](docs/RULES_INVENTORY.md) — project vs global vs User Rules.

### Creating work (epics, beads, roadmaps, PDRs)

| To create… | Template | Command |
|------------|----------|---------|
| Epic | [templates/EPIC_TEMPLATE.md](templates/EPIC_TEMPLATE.md) | `bd create "<title>" --type epic -p P1 -l <area>` |
| Bead | [templates/BEAD_TEMPLATE.md](templates/BEAD_TEMPLATE.md) | `bd create "<title>" --type task --parent <epic-id>` |
| Roadmap | [templates/ROADMAP_TEMPLATE.md](templates/ROADMAP_TEMPLATE.md) | → `docs/research/<TOPIC>_ROADMAP.md` |
| PDR | [08_PDRS/_PDR_TEMPLATE.md](08_PDRS/_PDR_TEMPLATE.md) | → `08_PDRS/<feature>.md` |
| Retro | [templates/RETRO_TEMPLATE.md](templates/RETRO_TEMPLATE.md) | → `docs/retros/YYYY-MM-DD-<slug>.md` |

Full template index: [templates/README.md](templates/README.md). After creating beads: `bd dolt commit` → `bd dolt push`.

---

## Session start (automated — hands-off)

Pre-session boot runs **without you running scripts daily**:

| Trigger | What runs |
|---------|-----------|
| **Cursor** new chat | `.cursor/hooks.json` → `session_boot_automation.py` |
| **Claude Code** session | `.claude/settings.json` → `session_start.py` → same boot |
| **Windows** daily 07:55 | Task `ChromaticSessionBoot` — `scripts/run_session_boot.ps1` |
| **CI** | `check_agent_operations.py` + `test_pre_session_activation.py` |

Boot steps (fast path): doc guard → MCP audit → manifest → intake validation → **context trim audit** (rebuild + `BOOT_CONTEXT.md` when risk is orange/red). Skips rework if `latest.json` is fresh (under 6 hours). Output: `07_LOGS_AND_AUDIT/pre_session/latest.json`, `.agents/context/context_trim_audit.json`.

Unified cross-surface guard (recommended default for IDE, CLI, MCP, and scheduler):

```bash
python scripts/session_unified_guard.py --surface auto --invoked-by automation
```

Receipt is written to `07_LOGS_AND_AUDIT/unified_guard/latest.json`.

**Context rebuild (manual or red-zone):**

```bash
python scripts/context_trim_audit.py
python scripts/context_rebuild.py --mode hard    # soft | hard | nuclear
python scripts/new_session_bootstrap.py
```

Policy: [docs/governance/CONTEXT_REBUILD_POLICY.md](docs/governance/CONTEXT_REBUILD_POLICY.md)

**One-time install (Task Scheduler):**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_automation_tasks.ps1
```

Optional PowerShell terminal startup hook (runs unified guard once per new terminal):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_session_guard_profile.ps1
```

**Agents still do at session start:**

```bash
bd prime
bd ready   # pick work from beads, not chat
```

Read handoff if present: `.agents/handoffs/latest.json`

> **Before creating any epic or bead, read [docs/playbooks/BEAD_EPIC_AUTHORING_PROTOCOL.md](docs/playbooks/BEAD_EPIC_AUTHORING_PROTOCOL.md)** (template: [templates/EPIC_BEAD_TEMPLATE.md](templates/EPIC_BEAD_TEMPLATE.md)). Key rules: PDR→plan→epic→beads order; **serialize `bd` writes** (Dolt is single-writer — parallel/background `bd` calls fail, and you must never remove the lock); priority is **P0–P4** (not 0–100); every child needs a ```` ```validation ```` block; waves form via `bd dep add`; never hand-author `[agent]` beads.

**Manual only when debugging or MCP plugins changed:**

```powershell
powershell -File scripts/session_preflight.ps1 -Full    # deep: context report log + bd ready
python scripts/session_boot_automation.py --force       # refresh manifest now
```

**Before each major swarm phase:**

```bash
python scripts/session_boot_automation.py --force
```

**One-command pre-swarm gate (repeatable):**

```bash
python scripts/pre_swarm_gate.py
```

This runs: forced boot refresh, `check_agent_operations`, `validate_governance_stack`, and `context_trim_audit`.

**Claude task delegation (router + T-level aware):**

```bash
python scripts/claude_delegate_gate.py --task "<objective>" --bead-id <id> --t-level T2 --privacy-class P1
```

Creates `.agents/handoffs/claude_delegate_packet.json` and `.agents/handoffs/claude_delegate_prompt.md` for repeatable Claude handoff.

| Step | Doc |
|------|-----|
| Handoff + compact rules | [12_HANDOFFS/SESSION_COMPACT.md](12_HANDOFFS/SESSION_COMPACT.md) |
| **Repo / rig map** | [docs/REPO_AND_RIG_INVENTORY.md](docs/REPO_AND_RIG_INVENTORY.md) — `scripts/audit_local_repos.ps1` |
| **Dev CLIs (all rigs)** | `powershell -File scripts/install_dev_clis.ps1` — `config/dev_cli_manifest.yaml` |
| **MCP disable / lean Claude** | [docs/CURSOR_CONTEXT_HYGIENE.md](docs/CURSOR_CONTEXT_HYGIENE.md) |
| **Do not trust / do not do** | [docs/AGENT_ANTIPATTERNS.md](docs/AGENT_ANTIPATTERNS.md) |
| **Implementation discipline** | [docs/governance/KARPATHY_DISCIPLINE.md](docs/governance/KARPATHY_DISCIPLINE.md) |
| Tools / MCP / CRG baseline | [docs/PRE_SESSION_AND_TOOLS.md](docs/PRE_SESSION_AND_TOOLS.md) |
| **Execution flow (canonical)** | [00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md](00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md) |
| **Context tiers (P0–P4)** | [docs/governance/PRE_SESSION_CONTEXT_POLICY.md](docs/governance/PRE_SESSION_CONTEXT_POLICY.md) |
| **Beads object model** | [docs/BEADS_OBJECT_MODEL.md](docs/BEADS_OBJECT_MODEL.md) |
| **OpenRouter broker** | [docs/governance/OPENROUTER_BROKER_POLICY.md](docs/governance/OPENROUTER_BROKER_POLICY.md) |
| **Pre-session manifest** | `07_LOGS_AND_AUDIT/pre_session/latest.json` — `scripts/pre_session_manifest.py --write` |
| **Router validation backlog** | [docs/beads/ROUTER_VALIDATION_BEADS.md](docs/beads/ROUTER_VALIDATION_BEADS.md) — `chromatic-harness-v2-gh1` (P1), `chromatic-harness-v2-uum` (P2) |
| Issue tracking | [AGENTS.md](AGENTS.md) (beads — not TodoWrite) |
| In-flight RPI | `.agents/rpi/execution-packet.json` (if exists) |
| Lite Claude workflows | `.claude/workflows/` → `scripts/sync_claude_workflows.ps1` |
| **GO modes (bounded runtime)** | `python scripts/workflow_go.py GO` or `/go` — [docs/workflows/GO_MODES.md](docs/workflows/GO_MODES.md); **no** unattended `GO SWARM` ([AGENT_ANTIPATTERNS](docs/AGENT_ANTIPATTERNS.md)) |

### Governance / GO (confidence + self-heal)

| Score | Decision | Action |
|------:|----------|--------|
| 0–49 | `halt` | Escalate |
| 50–69 | `self_heal` | `python scripts/workflow_self_heal_cycle.py` — GO → intake drain → GO again |
| 70–74 | `plan_only` | Manual `GO DEEP` or improve handoff |
| 75+ | `execute` | `/close-issue` or scoped implement (permission gate) |

Docs: [docs/governance/CONFIDENCE_GATE.md](docs/governance/CONFIDENCE_GATE.md), [docs/workflows/PERMISSION_GATE.md](docs/workflows/PERMISSION_GATE.md), [docs/governance/WORKFLOW_BUDGET_CONTRACT.md](docs/governance/WORKFLOW_BUDGET_CONTRACT.md). Validate: `python scripts/validate_governance_stack.py`. Daily audit: `python scripts/daily_harness_audit.py --root . --report` — [docs/governance/DAILY_AUDIT_RUNBOOK.md](docs/governance/DAILY_AUDIT_RUNBOOK.md).

### Git autonomy (tiered — no extra “please push” when gates pass)

| Step | Min confidence | Risk cap | Autonomous? |
|------|---------------|----------|-------------|
| Commit | 75 | not critical | Yes, via `workflow_git.py` |
| Push | 88 | not high/critical | Yes, after tests pass |
| Open PR | 85 | not high/critical | Yes, off main/master |
| Merge | 95 | low only + CI | Yes |

**Policy:** [docs/governance/GIT_AUTONOMY_POLICY.md](docs/governance/GIT_AUTONOMY_POLICY.md). **Always** `plan` before `ship --execute`. Cursor rule: `.cursor/rules/git-autonomy.mdc`.

| **Git ship (confidence-gated)** | `python scripts/workflow_git.py plan` → `ship --execute` — [docs/workflows/GIT_CONFIDENCE_PIPELINE.md](docs/workflows/GIT_CONFIDENCE_PIPELINE.md) |
| **Intake queue (close loop)** | [docs/INTAKE_QUEUE.md](docs/INTAKE_QUEUE.md) — `python scripts/auto_intake.py` |
| **Automation / ops** | [docs/ops/HARNESS_AUTOMATION_RUNBOOK.md](docs/ops/HARNESS_AUTOMATION_RUNBOOK.md) — `run_intake_cycle`, `smoke_stack`, Task Scheduler |
| **Hook architecture** | [docs/audit/HOOK_ARCHITECTURE.md](docs/audit/HOOK_ARCHITECTURE.md) — `python scripts/audit_hooks.py` |
| **Chromatic MCP (lite)** | [docs/CHROMATIC_MCP_SERVER.md](docs/CHROMATIC_MCP_SERVER.md) — one server vs 15 plugins |
| **Two-log audit** | [docs/workflows/TWO_LOG_AUDIT.md](docs/workflows/TWO_LOG_AUDIT.md) — `07_LOGS_AND_AUDIT/execution/` + `traces/` |
| **Activity log + dual backlog** | [docs/governance/ACTIVITY_LOG_AND_DUAL_BACKLOG.md](docs/governance/ACTIVITY_LOG_AND_DUAL_BACKLOG.md) — `python scripts/log_agent_activity.py log`; lanes: `python scripts/bd_ready_by_lane.py --lane human`; git triage: `python scripts/git_triage.py --from-log` |
| **Knowledge harvest** | `python scripts/harvest_rigs.py` — [docs/KNOWLEDGE_HARVEST.md](docs/KNOWLEDGE_HARVEST.md); runs on session handoff and after long-running loops |
| **Wiki (separate repo)** | [docs/WIKI_REPO_AND_PROMOTION.md](docs/WIKI_REPO_AND_PROMOTION.md) — `sync_wiki_mirror.py`, `promote_to_wiki.py`; beads [WIKI_V01](docs/beads/WIKI_V01_BEADS.md). After loop/shell incidents: `promote_to_wiki.py --execute` |
| **Session close-out / agent transfer** | `python scripts/session_closeout.py --invoked-by cursor` — [docs/SESSION_CLOSEOUT_CHECKLIST.md](docs/SESSION_CLOSEOUT_CHECKLIST.md), [docs/governance/AGENT_TRANSFER_POLICY.md](docs/governance/AGENT_TRANSFER_POLICY.md); auto-spawn: `CHROMATIC_AUTO_SPAWN=1` |
| **roach-pi runtime** | `python scripts/roach_pi_status.py` — [docs/ROACH_PI_RUNTIME.md](docs/ROACH_PI_RUNTIME.md); init via `init_roach_pi_submodule.ps1` |

**Brownfield:** Do not start a new RPI epic on top of in-flight work without reading the execution packet and checking the branch.

---

## MCP context (Cursor / native Claude)

**Cursor injects every enabled MCP’s tool schemas into every turn** (~tens of thousands of tokens). The harness CRG layer does **not** turn MCPs off in Cursor — you do.

| Action | Command / place |
|--------|-----------------|
| Audit token bulk | `python scripts/audit_mcp_context.py --profile harness_dev` |
| **Session context log** | `python scripts/session_context_report.py --log` |
| Profiles (what to disable) | `config/pre_session/mcp.profile.yaml` |
| Full guide | [docs/CURSOR_CONTEXT_HYGIENE.md](docs/CURSOR_CONTEXT_HYGIENE.md) |
| Disable server | Cursor **Settings → MCP** → toggle off (reversible) |
| Strict CI/local gate | `python scripts/audit_mcp_context.py --strict` |

**Daily harness dev:** disable at least Resend, Playwright, and Opsera MCPs (~43k+ tok combined). Re-enable only for email, browser, or security tasks.

**Workflows:** sync lite defaults — `powershell -File scripts/sync_claude_workflows.ps1`. Do **not** run heavy `/ship` (crank chain) or bulk-read `~/.claude/projects/**/*.jsonl`. See [docs/AGENT_ANTIPATTERNS.md](docs/AGENT_ANTIPATTERNS.md).

**Claude Code production (repo + machine):**

```powershell
powershell -File scripts/claude_harness_production_ready.ps1
python scripts/validate_claude_harness.py --machine
```

| Hook | Command |
|------|---------|
| SessionStart | `python scripts/session_start.py` (handoff + boot manifest) |
| SessionEnd | `python scripts/session_closeout.py --invoked-by claude_code` |
| PreCompact | `bd prime` |
| PreToolUse / Agent | `python 02_RUNTIME/router/gate.py` |

Global `~/.claude/settings.json` **stacks** with project hooks. Run `python scripts/slim_claude_global_hooks.py --apply` so Harness boot is not duplicated by four global SessionStart hooks. Restore: `--restore`.

---

## During work

| Rule | Why |
|------|-----|
| **Always proceed — never idle on a T1–T3 decision** | [CONTINUOUS_EXECUTION_SOP](docs/governance/CONTINUOUS_EXECUTION_SOP.md): at every task boundary, proceed to the next step or pull from `bd ready`. Only stop for T4 / hard blocks / explicit pause. Checker: `python scripts/continuous_execution_check.py` |
| Use `bd` for all tasks | Single source of truth for work |
| Review `bd ready` at every task boundary | Pick next work from beads; keep the ready queue clean (dedupe auto-generated noise) |
| Chat is not authoritative | Git + beads + handoff files hold facts |
| At ~50–65% context pressure | Run [compact checkpoint](12_HANDOFFS/SESSION_COMPACT.md#compact-checkpoint-65) |
| Before changing router/MCP/CRG | Regenerate inventory (below) |
| Before long Cursor sessions | Run MCP audit; disable unused plugins |

---

## Before changing tools, MCP, or CRG (required)

```bash
python scripts/generate_pre_session_inventory.py
python scripts/check_agent_operations.py
git diff config/pre_session/inventory.snapshot.json docs/PRE_SESSION_AND_TOOLS.md
```

Then update policy code if needed:

- `02_RUNTIME/router/context_manifest.py` — resource IDs
- `09_DEPLOYMENT/config/routing/context-policy.yaml` — task rules
- `01_PROTOCOLS/MCP/MCP_TOOL_MANIFEST.md` — harness MCP families

Run: `pytest tests/test_context_*.py tests/test_pre_session_inventory_script.py`

---

## Session end (required)

1. File/close beads issues  
2. Quality gates (`pytest`, `ruff` if code changed)  
3. **Git** — run `workflow_git.py plan`; if push allowed (conf ≥ 88, tests green, risk not high/critical), `ship --execute` **without waiting for a separate “please push”** ([GIT_AUTONOMY_POLICY](docs/governance/GIT_AUTONOMY_POLICY.md))  
4. If gates block push, hand off with staged commits and explicit next command  
5. **Hand off** — [SESSION_COMPACT](12_HANDOFFS/SESSION_COMPACT.md) + `.agents/handoffs/latest.json`

Agent Lead synthesis (missions with magnet events):

```http
POST /missions/{mission_id}/synthesize?create_bead=true
```

---

## Role-specific playbooks

| Role | Playbook |
|------|----------|
| GO / autonomous | [04_PLAYBOOKS/GO_MODE_PLAYBOOK.md](04_PLAYBOOKS/GO_MODE_PLAYBOOK.md) |
| Orchestrator | [04_PLAYBOOKS/ORCHESTRATOR_PLAYBOOK.md](04_PLAYBOOKS/ORCHESTRATOR_PLAYBOOK.md) |
| Magnets | [04_PLAYBOOKS/MAGNETS_PLAYBOOK.md](04_PLAYBOOKS/MAGNETS_PLAYBOOK.md) |
| Session compact | [04_PLAYBOOKS/SESSION_COMPACT_PLAYBOOK.md](04_PLAYBOOKS/SESSION_COMPACT_PLAYBOOK.md) |
| Agent registry | [03_AGENTS/AGENT_REGISTRY.md](03_AGENTS/AGENT_REGISTRY.md) |

---

## CI / automation

`scripts/check_agent_operations.py` runs in GitHub Actions. PRs fail if mandatory docs or cross-links are removed.

`pytest tests/test_pre_session_activation.py` enforces manifest + intake contract.

---

## Is pre-session active? (checklist)

| Check | Evidence |
|-------|----------|
| Automation installed | `schtasks /Query /TN ChromaticSessionBoot` or Cursor hooks present |
| Boot ran recently | `07_LOGS_AND_AUDIT/pre_session/latest.json` `generated_at` within 6h (or new Cursor chat) |
| Doc pack intact | CI / `check_agent_operations.py` exits 0 |
| MCP cost reviewed | `mcp_audit` in manifest; heavy MCPs off in Cursor Settings |
| Work from beads | `bd ready` / claimed issue — not chat TODOs |
| Agent used P0 docs | Cites `AGENT_OPERATIONS` + `HARNESS_EXECUTION_FLOW`; no bulk load of `GOVERNANCE_AND_ROUTING_ARCHITECTURE` unless routing work |

---

## One-line summary

**Start:** handoff → bd → git → audit MCPs → **manifest**. **Change tools:** regenerate inventory + check script. **End:** test → beads → push → handoff.
