# Hook Architecture — Best Practices

Canonical guide for lifecycle hooks vs workflows vs rules in Chromatic Harness v2.

**Re-audit:** `python scripts/audit_hooks.py`  
**Latest report:** [HOOK_AUDIT_LATEST.md](HOOK_AUDIT_LATEST.md) (regenerate with `--markdown`)

---

## Layer model

| Layer | Location | Owns | Must not own |
|-------|----------|------|----------------|
| **Global** | `~/.claude/settings.json` | Cross-repo safety, compaction, usage/stop | Repo-specific `gate.py` paths |
| **Project** | `.claude/settings.json` | `session_start`, `bd prime`, relative `gate.py` | Duplicates of global Bash/context hooks |
| **Local** | `.claude/settings.local.json` (gitignored) | Personal SessionStart slim mode | Secrets |
| **Cursor** | `.cursor/hooks.json` | `sessionStart` → boot only | Full Claude hook parity |
| **OS** | Task Scheduler | Boot/intake when IDE closed | Interactive `bd ready` |
| **CI** | `.github/workflows/ci.yml` | Doc guards + hook audit (no HIGH) | IDE session hooks |

```text
Global (safety) → Project (harness) ← Cursor (boot) ← Task Scheduler
CI guards contract on every push/PR
```

---

## Project hooks (committed)

[`.claude/settings.json`](../../.claude/settings.json):

| Event | Matcher | Command | Timeout |
|-------|---------|---------|---------|
| SessionStart | (all) | `python scripts/session_start.py` | 120s |
| PreCompact | (all) | `bd prime` | 30s |
| PreToolUse | Agent | `python 02_RUNTIME/router/gate.py` | 10s |

[`.cursor/hooks.json`](../../.cursor/hooks.json): `sessionStart` → `.cursor/hooks/session_boot.py` (120s).

---

## Global `~/.claude/settings.json` — required edit (one-time)

**Remove** the harness-specific duplicate `PreToolUse` / `Agent` block. `gate.py` must run **only** from the project settings above.

### Delete this block from `PreToolUse` array

```json
{
  "matcher": "Agent",
  "hooks": [
    {
      "type": "command",
      "command": "python C:/Users/kas41/chromatic-harness-v2/02_RUNTIME/router/gate.py",
      "timeout": 5
    }
  ]
}
```

### Keep in global (do not remove)

- `PreToolUse` / `Bash` — `pre-commit.sh`, `policy_gate.py`
- `PreToolUse` catch-all — `injection-guard.sh`
- `SessionStart` flywheel hooks — `ao.sh`, prompt-db, ollama-liveness, session-health
- `Stop`, `UserPromptSubmit`, `PostToolUse`, `PreCompact` guidance

### Verify after edit

```bash
python scripts/audit_hooks.py
```

Expect: **no HIGH** finding for duplicate Agent gate.

---

## SessionStart slim mode (optional)

Global SessionStart hooks still run in every repo (~4 hooks). For long harness-only sessions:

1. Copy [`.claude/settings.local.json.example`](../../.claude/settings.local.json.example) to `.claude/settings.local.json`
2. Confirm Claude Code merge behavior on your version (local may merge or replace SessionStart)
3. If merge is additive, temporarily disable global SessionStart in user settings during deep harness work

Harness boot remains in project `session_start.py` (calls `session_boot_automation.py`).

---

## Workflows (not lifecycle hooks)

[`.claude/workflows/`](../../.claude/workflows/) are **slash commands** (`/ship`, `/qa`, `/close-issue`). They do not run on session open.

| Workflow | Est. tokens | Notes |
|----------|-------------|-------|
| `/ship` | ~50–150k | No `/crank` |
| `/close-issue` | ~30–80k | Single bead |
| `/qa` | ~10–30k | pytest + ruff |
| `/go` | ~30–80k | Bounded GO |
| `*.HEAVY.js.bak` | High | Archived — do not restore |

See [docs/AGENT_ANTIPATTERNS.md](../AGENT_ANTIPATTERNS.md).

---

## What is NOT a hook

- `.cursor/rules/*.mdc` with `alwaysApply: true`
- `AGENTS.md` / `CLAUDE.md`
- Enabled MCP tool schemas in Cursor
- GitHub Actions steps on push/PR

---

## Checklist before adding a hook

- [ ] Correct **event** (narrowest that fits)
- [ ] **Matcher** only if needed (avoid catch-all PostToolUse)
- [ ] **timeout** set (PreToolUse ≤ 10s, SessionStart ≤ 120s)
- [ ] Repo-relative path in **project** file only
- [ ] Not duplicated in global + project
- [ ] Run `python scripts/audit_hooks.py` after change

---

## Automation (hands-off)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_automation_tasks.ps1
```

| Task | Schedule |
|------|----------|
| ChromaticSessionBoot | Daily 07:55 |
| ChromaticIntakeCycle | Every 15 min |
| ChromaticSessionPreflight | Weekly Mon 09:00 (Full) |

See [docs/ops/HARNESS_AUTOMATION_RUNBOOK.md](../ops/HARNESS_AUTOMATION_RUNBOOK.md).

If `install_automation_tasks.ps1` fails with schtasks errors, run PowerShell **as Administrator** or create tasks manually in Task Scheduler pointing at the scripts above.
