# Agent Antipatterns — Do Not Trust / Do Not Do

> **Mandatory reading** with [AGENT_OPERATIONS.md](../AGENT_OPERATIONS.md) and [CURSOR_CONTEXT_HYGIENE.md](CURSOR_CONTEXT_HYGIENE.md).  
> These mistakes caused a **~1.3M token** Claude session (skill audit + transcript mining + heavy workflows).

---

## Do not trust

| You might think… | Reality |
|------------------|---------|
| **CRG / ContextGate limits what Claude sees** | CRG only governs harness **router API** and Pi advisories. Cursor still injects **all enabled MCP schemas** every turn. |
| **Skills are pull-on-read only** | Cursor and Claude Code still send a **skill catalog** (names + blurbs) in instruction context. Attaching a skill in chat **inlines the full SKILL.md** (e.g. `/rpi` ~4k tok, `/post-mortem` ~7k tok). |
| **Chat memory is authoritative** | **Git + beads + handoff files** hold facts. Re-read `bd show`, `git log`, `.agents/handoffs/latest.json`. |
| **`.beads/issues.jsonl` is source of truth** | Passive export. Use **`bd`** commands only. |
| **MCP folders on disk = disabled** | Descriptors can remain on disk when toggled off in UI. **Audit measures upper bound** if everything were enabled. |
| **`/ship` or workflows are “one command convenience”** | Heavy workflows chain **subagents + council + crank** → **500k–2M+ tokens** per run. |
| **Scanning `~/.claude/projects/**/*.jsonl` is harmless** | **~370MB / ~92M tokens** on disk. Partial reads still burn **hundreds of thousands to millions**. |
| **Running validate.sh on 54 skills in one session is cheap** | Each skill + bash output + tables → **large tool-result context** every turn. |
| **Agent Lead `halt` means stop spending tokens** | Missions can halt while the **chat session** keeps growing. Compact and start fresh. |
| **More MCPs = more capability, little cost** | Resend MCP alone was **~31k tokens** of schemas before the first message. |

---

## Do not do

### Context & tokens

- [ ] Bulk-read **`~/.claude/projects/**/*.jsonl`** or **`~/.claude/history.jsonl`** for “usage analysis”
- [ ] Run **full skill MVS audit** (54 skills × validate.sh) inside an agent session
- [ ] Attach **`/rpi`**, **`/crank`**, **`/post-mortem`**, **`/council`** skills to messages unless executing that phase **now**
- [ ] Leave **15+ MCP servers enabled** during daily harness dev
- [ ] Ignore **`session_context_report.py` warnings** (>12k MCP estimate)

### Workflows (Claude Code)

- [ ] Run **`/ship`** with the **heavy** chain (discovery → plan → **crank** → vibe → release)
- [ ] Use **`agent()`** workflows that **paste entire prior phase output** into the next prompt
- [ ] Chain **`/crank`** (runs until all beads closed; spawns subagents)
- [ ] Chain **`/vibe --deep`** + **`/post-mortem --deep`** in one unattended run
- [ ] Run **`/qa`** with parallel complexity + security + perf + vibe without a scoped changeset
- [ ] Run **`GO SWARM`** or **`/go`** with parallel agents without an **approved task graph** and human gate

### Harness discipline

- [ ] Use **TodoWrite** or markdown TODO lists instead of **`bd`**
- [ ] Start a **new RPI epic** without reading `.agents/rpi/execution-packet.json`
- [ ] Treat **compaction** as optional on long sessions
- [ ] Say **“ready to push when you are”** — **you push** per AGENTS.md

---

## Do instead

| Goal | Safe pattern | Est. cost |
|------|--------------|-----------|
| Start session | `session_context_report.py --log`, `bd ready`, read handoff | Low |
| Plan feature | **`/ship-lite`** or `/plan` only → beads issues | ~50–150k |
| Close one issue | **`/close-issue`** (repo workflow) or `/implement` + pytest | ~30–80k |
| Quality check | **`pytest` + `ruff`**; optional `/vibe --quick` on changed files | ~20–50k |
| Hotfix | **`/hotfix`** (lite) or `/bug-hunt` then minimal patch | ~40–100k |
| Epic execution | **`bd ready`** → one issue at a time → **`/close-issue <id>`** | Bounded |
| Next safest task | **`python scripts/workflow_go.py GO`** or lite **`/go`** | ~30–80k |
| Full autonomous epic | Explicit human gate; never unattended **`/crank`** | — |

Repo workflows: [`.claude/workflows/README.md`](../.claude/workflows/README.md)

---

## Workflow cost reference

| Workflow | Chain | Risk |
|----------|-------|------|
| **ship.HEAVY** (archived) | discovery → plan → **crank** → vibe → release + post-mortem | **500k–2M+** |
| **ship** (lite, default) | discovery → plan → handoff pointer | ~50–150k |
| **qa.HEAVY** (archived) | complexity ∥ security ∥ perf → vibe | ~200–500k |
| **qa** (lite) | pytest + ruff summary | ~10–30k |
| **close-issue.HEAVY** (archived) | implement → test ∥ vibe → post-mortem → push | ~150–400k |
| **close-issue** (lite) | implement → pytest → push | ~30–80k |
| **go** (lite) | workflow_go GO → one agent → GO VERIFY | ~30–80k |

---

## Sync safe workflows to Claude Code

From repo root:

```powershell
# Windows — backs up heavy workflows, installs repo lite versions
powershell -File scripts/sync_claude_workflows.ps1
```

```bash
# Unix
bash scripts/sync_claude_workflows.sh
```

Target: `~/.claude/workflows/` (user-global Claude Code).

---

## Related

- [CURSOR_CONTEXT_HYGIENE.md](CURSOR_CONTEXT_HYGIENE.md)
- [AGENT_OPERATIONS.md](../AGENT_OPERATIONS.md)
- [SESSION_COMPACT.md](../12_HANDOFFS/SESSION_COMPACT.md)
