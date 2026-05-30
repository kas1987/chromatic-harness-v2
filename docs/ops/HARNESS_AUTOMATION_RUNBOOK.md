# Harness Automation Runbook

> **Epic:** `chromatic-harness-v2-7d2` — Post-merge production hardening  
> **Retro:** [2026-05-29 session ROI / production readiness](../retros/2026-05-29-session-roi-production-readiness.md)

Local recurring automation uses **Windows Task Scheduler** ($0). **GitHub Actions** runs on **push/PR only** (no scheduled cron — saves Actions minutes on private repos).

---

## Prerequisites

| Tool | Purpose |
|------|---------|
| Docker Desktop | `09_DEPLOYMENT/docker-compose.yml` stack |
| Python 3.12+ | Scripts under `scripts/` |
| `bd` (beads) | `auto_intake` creates/claims issues |
| Dev CLIs (all rigs) | `powershell -File scripts/install_dev_clis.ps1` — see `config/dev_cli_manifest.yaml` |
| `.env` in `09_DEPLOYMENT/` | Copy from [`.env.example`](../../09_DEPLOYMENT/.env.example) |

Optional auth for API testing:

```env
AUTH_ENABLED=true
JWT_SECRET=<strong-secret>
```

---

## Close loop (manual or scheduled)

```text
producers -> intake_queue.jsonl -> poll_inbox -> auto_intake -> bd ready -> workflow_go
```

### One command (Windows)

```powershell
powershell -NoProfile -File scripts/run_intake_cycle.ps1
```

### One command (WSL / Linux)

```bash
bash scripts/run_intake_cycle.sh
```

Defaults: `--limit 10` on poll and auto_intake. Override: `$env:CHROMATIC_INTAKE_LIMIT = 20`

### Audit log

Append-only JSONL (gitignored):

```text
07_LOGS_AND_AUDIT/intake_cycle/cycle_YYYYMMDD.jsonl
```

### Validate contract (no live bd)

```bash
python scripts/validate_intake_loop.py
```

### After beads are ready

```bash
bd ready
python scripts/workflow_go.py "GO VERIFY"
```

### Self-heal closed loop (optional)

When `workflow_go GO` returns `decision: self_heal` (confidence 50–69), drain intake and re-score:

```bash
python scripts/workflow_self_heal_cycle.py
python scripts/workflow_self_heal_cycle.py --limit 20
```

`/go` in Claude Code runs this cycle automatically. After `run_intake_cycle.ps1`, run the self-heal cycle if the last workflow log shows `self_heal`.

Full governance gates: `python scripts/validate_governance_stack.py`

---

## Stack smoke (bounded timeouts)

```powershell
powershell -NoProfile -File scripts/smoke_stack.ps1
# Skip slow console warm-up:
powershell -NoProfile -File scripts/smoke_stack.ps1 -SkipConsole
```

Expect: API `http://127.0.0.1:8787/health` returns 2xx within 10s.

Start stack:

```bash
cd 09_DEPLOYMENT
docker compose up -d --build
```

Console uses production build ([`Dockerfile.console`](../../09_DEPLOYMENT/Dockerfile.console)), not `npm run dev`.

---

## Pre-session (hands-off — default)

You do **not** need to run preflight daily. Boot is automatic:

| Trigger | Mechanism |
|---------|-----------|
| Cursor new chat | `.cursor/hooks.json` → `session_boot_automation.py` |
| Claude Code | `session_start.py` on SessionStart |
| Windows daily 07:55 | Task `ChromaticSessionBoot` |

**Install tasks once:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_automation_tasks.ps1
```

Manifest: `07_LOGS_AND_AUDIT/pre_session/latest.json` (refreshed when older than 6h unless `--force`).

**Manual deep preflight** (debug / `-StrictMcp`):

```powershell
powershell -NoProfile -File scripts/session_preflight.ps1 -Full
```

```bash
bash scripts/session_preflight.sh
```

WSL quick boot only: `bash scripts/run_session_boot.sh`

See [CURSOR_CONTEXT_HYGIENE.md](../CURSOR_CONTEXT_HYGIENE.md), [PRE_SESSION_CONTEXT_POLICY.md](../governance/PRE_SESSION_CONTEXT_POLICY.md), and [HOOK_ARCHITECTURE.md](../audit/HOOK_ARCHITECTURE.md).

**Hooks vs Scheduler:** IDE hooks (`sessionStart`, Claude `SessionStart`) run when you open a session; Task Scheduler runs boot/intake when the IDE is closed.

---

## Windows Task Scheduler

Install (idempotent):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_automation_tasks.ps1
```

| Task | Schedule | Script |
|------|----------|--------|
| `ChromaticIntakeCycle` | Every 15 min | `run_intake_cycle.ps1` |
| `ChromaticSmokeDaily` | Daily 08:00 | `smoke_stack.ps1` |
| `ChromaticSessionPreflight` | Weekly Mon 09:00 | `session_preflight.ps1` |

Verify:

```powershell
schtasks /Query /TN ChromaticIntakeCycle
```

Machine must be on for tasks to run.

---

## GitHub Actions (push / PR only)

[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml):

- Submodules (roach-pi)
- `check_agent_operations.py`
- `validate_intake_loop.py`
- ruff, mypy, pytest
- PR only: `workflow_git.py plan` artifact (dry-run, no execute)

No scheduled cron workflows in this repo.

---

## Git ship (manual only)

| Action | Command | Automate? |
|--------|---------|-----------|
| Plan | `python scripts/workflow_git.py plan --confidence 92 --verifier approve --tests-passed` | CI dry-run on PR |
| Execute ship | `workflow_git.py ship --execute` | **Never** in Task Scheduler |

Policy gates: [GIT_CONFIDENCE_PIPELINE.md](../workflows/GIT_CONFIDENCE_PIPELINE.md)

---

## Do not automate

Per [AGENT_ANTIPATTERNS.md](../AGENT_ANTIPATTERNS.md):

- `/crank`, council skills, unattended `GO SWARM`
- `workflow_git ship --execute` on a schedule
- Enabling 15+ MCP servers for daily dev

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Intake cycle fails | `07_LOGS_AND_AUDIT/intake_cycle/*.jsonl`, run `poll_inbox --dry-run` |
| `bd` missing | Install beads CLI; `bd prime` |
| API smoke fails | `docker compose ps`, `docker compose logs chromatic-api` |
| Console slow | First prod build ~90s; use `-SkipConsole` or wait for healthcheck |
| CI not running | Repo Settings → Actions enabled; push to non-main branch |

---

## P3 (deferred)

After ~1 week stable ops: autonomy L0–L5 (`7d2.6`), playbook evolution (`7d2.5`), MCP ecosystem (`7d2.7`). Track with `bd show chromatic-harness-v2-7d2`.
