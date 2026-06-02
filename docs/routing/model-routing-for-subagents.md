# Model Routing for Subagents (on-demand detail)

> Loaded on demand. The lean pointer lives in `~/.claude/CLAUDE.md`. Read this
> when dispatching subagents/workflows and you need the full routing table.
> Companion: `~/.claude/governance/subagent-token-efficiency.md` (the 5 rules).

**Canonical matrix:** `chromatic-harness-v2/docs/routing/multi-router-matrix.yaml`  
(federate via `bash chromatic-harness-v2/scripts/federate-governance.sh`; this file is a federated copy).
Global default implements tiers 0–4 via `model-router.sh` + `router-patterns.json`.
**chromatic-harness-v2 supersedes this locally** with a typed Python router (`02_RUNTIME/router/gate.py`)
that separates task complexity (C1–C4) from provider cost/availability (T0–T4); see `GOVERNANCE_AND_ROUTING_ARCHITECTURE.md`.

User runs an Ollama-based "OL layer" on their desktop. When dispatching subagents
via the `Agent` tool, choose the cheapest model that can succeed:

**Route to local OL (use `model: "haiku"` and the `model-router.sh` hook will tag
for OL routing):**
- Mechanical implementation: file-with-given-content, scaffold-from-template,
  seed-data creation (slash command markdowns, fixture files, README boilerplate)
- Spec compliance reviewer for trivial/boilerplate tasks
- Code quality reviewer for single-file boilerplate
- Knowledge forge / dedup / classification (markdown frontmatter, tag inference)
- Status report formatting / JSON-to-table rendering
- Test runner + result parsing (when the test command is given verbatim)

**Stay on cloud (use `model: "sonnet"` or `"opus"`):**
- Brainstorming, design, plan-writing
- Pre-mortem / risk analysis / candidate ranking
- Multi-file integration logic
- Cross-file refactor decisions
- Debugging novel issues / root-cause analysis
- Spec compliance review for integration tasks (multi-module)
- Conversation orchestration / tool dispatch (the orchestrator itself — never
  route the foreman, only the workers)

**No LLM at all (use direct shell, not Agent dispatch):**
- `ls`, `grep`, `git status`, `git log`, `find` — use Bash/Glob/Grep tools
- `jq`, `yq`, JSON pretty-print
- File existence checks
- Markdown frontmatter parse (use `template_loader.py` if extant)
- Test runner invocation (when no LLM judgment needed on output)

## Effort Level Routing (addendum 2026-06-02)

Full reference: `C:\.00_True_AI\model-effort-routing.md` | CSV: `model-effort-routing.csv`

**Rule:** Classify C-level first, then set the minimum effort the task actually requires.
Subagents do NOT inherit session effort automatically — set it explicitly per dispatch.

| Model + Effort | Est. Cost | Route When |
|---|---|---|
| Haiku / any | $0.001–0.01 | C1–C2 mechanical — effort is a no-op for Haiku |
| Sonnet / low-medium | $0.02–0.15 | C2–C3 standard coding, review, debug |
| Sonnet / high | $0.15–0.40 | C3–C4 deep reasoning (inference-chain tasks) |
| Sonnet / max | $0.30–0.80 | C4 exhaustive — but check Opus low first |
| **Opus / low** | **$0.10–0.25** | **C4 creative/knowledge tasks AND crossover zone — often cheapest C4 option** |
| Opus / medium-high | $0.20–1.50 | C4 high-trust decisions, security audits |
| Opus / max | $1.00–3.00 | C4 mission-critical — gate required |

**Crossover rule:** `Sonnet high ≈ Opus low` for **reasoning-bound** C3–C4 tasks.
But `Opus low` is **cheaper** (~$0.10–0.25 vs $0.30–0.80) at that crossover point.
For **knowledge-bound** tasks (synthesis, creativity, judgment), the crossover fails — Opus wins.

**Heuristic:** If the prompt is >70% reference material the agent must copy
verbatim and <30% judgment, route local. If it asks for novel decisions or
analysis of unfamiliar code, route cloud.

**Cache discipline:** Don't break the cloud cache prefix to chase local routing —
route via subagent dispatches and hooks (ephemeral side-channels), not
mid-conversation parent handoffs.

The `~/.claude/hooks/model-router.sh` PreToolUse hook observes Agent dispatches
and writes routing recommendations to `~/.claude/.agents/router/log.jsonl` for
the OL layer to consume. By default the hook only advises; with `ROUTER_BLOCK_ENABLED=true` (currently set in settings.json), it also emits `permissionDecision:deny` for pure-LLM `general-purpose` dispatches that target a sub-tier-4 model.
