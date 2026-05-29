# Agent Operations — Mandatory for All Harness Agents

> **Applies to:** Claude, Pi, Codex, Cursor agents, and every runtime in Chromatic Harness v2.  
> **If you skip this, you will break governance, miss MCP/CRG changes, or strand work.**

This is the single entry point. Sub-docs go deeper; this page is the checklist nothing is allowed to skip.

---

## Session start (every agent, every session)

```bash
# 1. Resume context (if prior session)
cat .agents/handoffs/latest.json 2>/dev/null && type .agents/handoffs/latest.json

# 2. Issue tracker
bd prime
bd ready

# 3. Git reality
git branch --show-current
git status --short

# 4. Trim MCP context (Cursor / Claude — even without harness API)
python scripts/audit_mcp_context.py --profile harness_dev

# 5. Know your tool surface (again after MCP plugin changes)
#    docs/PRE_SESSION_AND_TOOLS.md
```

| Step | Doc |
|------|-----|
| Handoff + compact rules | [12_HANDOFFS/SESSION_COMPACT.md](12_HANDOFFS/SESSION_COMPACT.md) |
| **MCP disable / lean Claude** | [docs/CURSOR_CONTEXT_HYGIENE.md](docs/CURSOR_CONTEXT_HYGIENE.md) |
| Tools / MCP / CRG baseline | [docs/PRE_SESSION_AND_TOOLS.md](docs/PRE_SESSION_AND_TOOLS.md) |
| Issue tracking | [AGENTS.md](AGENTS.md) (beads — not TodoWrite) |
| In-flight RPI | `.agents/rpi/execution-packet.json` (if exists) |

**Brownfield:** Do not start a new RPI epic on top of in-flight work without reading the execution packet and checking the branch.

---

## MCP context (Cursor / native Claude)

**Cursor injects every enabled MCP’s tool schemas into every turn** (~tens of thousands of tokens). The harness CRG layer does **not** turn MCPs off in Cursor — you do.

| Action | Command / place |
|--------|-----------------|
| Audit token bulk | `python scripts/audit_mcp_context.py --profile harness_dev` |
| Profiles (what to disable) | `config/pre_session/mcp.profile.yaml` |
| Full guide | [docs/CURSOR_CONTEXT_HYGIENE.md](docs/CURSOR_CONTEXT_HYGIENE.md) |
| Disable server | Cursor **Settings → MCP** → toggle off (reversible) |
| Strict CI/local gate | `python scripts/audit_mcp_context.py --strict` |

**Daily harness dev:** disable at least Resend, Playwright, and Opsera MCPs (~43k+ tok combined). Re-enable only for email, browser, or security tasks.

**Claude Code hooks** (`.claude/settings.json`): `session_start.py` prints handoff; `gate.py` on Agent dispatch for CRG advisory.

---

## During work

| Rule | Why |
|------|-----|
| Use `bd` for all tasks | Single source of truth for work |
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

Per [AGENTS.md → Session Completion](AGENTS.md#session-completion):

1. File/close beads issues  
2. Quality gates (`pytest`, `ruff` if code changed)  
3. **Commit** (when appropriate)  
4. **Push** — work is not done until push succeeds  
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

---

## One-line summary

**Start:** handoff → bd → git → audit MCPs. **Change tools:** regenerate inventory + check script. **End:** test → beads → push → handoff.
