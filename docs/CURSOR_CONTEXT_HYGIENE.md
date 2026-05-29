# Cursor & Claude Context Hygiene

> **Works with or without the full harness runtime.**  
> Trim what Cursor injects *before* the first message — CRG and router gates cannot fix MCP bloat inside Cursor.

---

## The problem

Cursor loads into **instruction context** every turn:

| Source | Typical cost | Harness controls it? |
|--------|-------------:|:--------------------:|
| `AGENTS.md`, `CLAUDE.md`, rules | 2k–8k+ tok | Docs only |
| Agent skill **catalog** (names/blurbs) | 10k–40k+ tok | Pull-on-read policy in docs |
| **MCP tool JSON schemas** (enabled servers) | **5k–50k+ tok** | **You** (Cursor MCP settings) |
| Native tool schemas | (in Cursor system) | No |
| CRG manifest (router model) | ≤6.5k tok | Yes — API/Pi only |

On a typical machine with 15 MCP plugins, descriptor bulk alone was **~47k tokens**; Resend MCP alone was **~31k**.

---

## Disable vs delete vs “add back later”

| Action | What happens | When to use |
|--------|--------------|-------------|
| **Disable** (recommended) | Cursor Settings → **MCP** → toggle server **off**. Descriptors may remain on disk but are **not injected**. | Daily harness work; “sometimes use” tools |
| **Uninstall plugin** | Removes plugin; may remove `mcps/<server>` folder. Reinstall from Cursor marketplace later. | Plugins you rarely need |
| **Delete `mcps` folder entry** | Manual delete under `.cursor/projects/<project>/mcps/<server-id>/`. Cursor may recreate if plugin stays installed. | Cleanup after uninstall |
| **Profile `harness_full`** | Document only — enable everything when doing email/SRE/browser tasks | Short focused sessions |

**Do not** delete harness repo files to save context — MCP descriptors live in **Cursor’s project cache**, not in `chromatic-harness-v2`.

---

## Recommended workflow (native Claude in Cursor)

### 1. Pick a profile

| Profile | Use when | MCP |
|---------|----------|-----|
| `harness_dev` | Default coding, beads, pytest, router | **None** (or GitHub only for PRs) |
| `harness_github` | PRs, `gh`, issues | GitHub MCP |
| `harness_email` | Resend / inbox features | Resend |
| `harness_browser` | UI tests | Playwright |
| `harness_security` | Pre-release scan | Opsera |
| `harness_full` | Everything | All (high context) |

Defined in `config/pre_session/mcp.profile.yaml`.

### 2. Audit your machine

```bash
# Copy settings.example.yaml → settings.local.yaml and set mcp_descriptors_path
python scripts/audit_mcp_context.py --profile harness_dev
python scripts/audit_mcp_context.py --strict   # exit 1 if still too heavy
```

### 3. Disable heavy MCPs in Cursor UI

For `harness_dev`, turn **off** at minimum:

- `plugin-resend-resend` (~31k tok)
- `plugin-playwright-playwright` (~5k tok)
- `plugin-opsera-devsecops-opsera` (~7k tok)

Full list: `disable_for_daily_dev` in `mcp.profile.yaml`.

Use **Shell + `gh`** instead of GitHub MCP when you only need CLI operations.

### 4. Session start (automatic if using repo hooks)

`.claude/settings.json` runs `scripts/session_start.py`:

- Prints `.agents/handoffs/latest.json`
- Runs `bd prime`

### 5. Subagent dispatch (optional advisory)

`PreToolUse` → `02_RUNTIME/router/gate.py` adds CRG + provider notes on **Agent** tool calls.

Set `ROUTER_CONTEXT_MAX_TOKENS=128000` (default) so CRG does not false-block coding tasks.

---

## Running Claude **without** the harness API

You still get value from:

| Mechanism | Location |
|-----------|----------|
| Lean MCP surface | Cursor settings + audit script |
| Beads + handoff | `bd`, `.agents/handoffs/latest.json` |
| Session compact | `12_HANDOFFS/SESSION_COMPACT.md` |
| Agent rules | `AGENT_OPERATIONS.md`, `CLAUDE.md` |
| No TodoWrite | `AGENTS.md` |

You do **not** need Docker, FastAPI, or magnets for context hygiene.

---

## Harness router / CRG (when API or Pi is used)

- `ContextGate` budgets **allowed resource descriptions**, not Cursor MCP JSON.
- Default route `max_tokens` in tests: **128000**; budget = 25% → **32k** for CRG bundle.
- Pi `gate.py` uses `ROUTER_CONTEXT_MAX_TOKENS` (same default) so advisories are not false `CRG BLOCKED`.

---

## CI / team

```bash
python scripts/check_agent_operations.py
python scripts/audit_mcp_context.py --mcps-path tests/fixtures/mcp_minimal
pytest tests/test_audit_mcp_context.py -q
```

PRs should not delete hygiene docs. Use **fixture MCP path** in CI (minimal tokens).

---

## Checklist before a long session

- [ ] `python scripts/audit_mcp_context.py --profile harness_dev`
- [ ] Disable unused MCPs in Cursor
- [ ] `cat .agents/handoffs/latest.json` (or open after SessionStart hook)
- [ ] `bd ready`
- [ ] Re-enable MCPs only for the task (email, browser, etc.)

---

## Related

- [PRE_SESSION_AND_TOOLS.md](PRE_SESSION_AND_TOOLS.md)
- [AGENT_OPERATIONS.md](../AGENT_OPERATIONS.md)
- [SESSION_COMPACT.md](../12_HANDOFFS/SESSION_COMPACT.md)
