# Repo and Rig Inventory

> **Regenerate:** `powershell -File scripts/audit_local_repos.ps1`  
> **Last audit:** 2026-05-29 (manual + script)  
> **Standards:** [AGENT_OPERATIONS.md](../AGENT_OPERATIONS.md), [12_HANDOFFS/SESSION_COMPACT.md](../12_HANDOFFS/SESSION_COMPACT.md)

Canonical map of Chromatic repos on this machine vs GitHub (`kas1987`), with harness v2 alignment checks.

---

## Alignment rubric

| Check | Meaning |
|-------|---------|
| `AGENTS.md` | Agent entry point |
| `CLAUDE.md` | Claude/Cursor project instructions |
| `.agents/` | Knowledge + handoff tree |
| `knowledge` | `.agents/{learnings,patterns,research}/` (harvest-eligible) |
| `handoff` | `.agents/handoffs/latest.json` |
| `beads` | `.beads/` + `bd` workflow |
| `remote` | `git remote get-url origin` |
| **Aligned** | All harness-critical checks pass |

**System of record:** `chromatic-harness-v2` only.

---

## Tier 1 — Local git projects

| Project | Path | GitHub | Branch | Role | Alignment |
|---------|------|--------|--------|------|-----------|
| Chromatic Harness v2 | `C:\Users\kas41\chromatic-harness-v2` | `kas1987/chromatic-harness-v2` | `session/chromatic-harness-v2-initial` | Primary harness | **Aligned** |
| Fusion Computer | `C:\Users\kas41\fusion-computer` | `kas1987/fusion-computer` | `session/2026-05-28-harness-v2` | Templates & standards rig | Partial — beads N/A; no handoff |
| Claude config | `C:\Users\kas41\.claude` | `kas1987/claude-config` | `session/mc-x1bi-governance-fixes` | Global Claude config | Partial — no handoff |
| Chromatic stack | `C:\Users\kas41\chromatic-stack` | `kas1987/chromatic-stack` | `session/repo-governance-20260530` | Docker local agent stack | **Partial** — beads + handoff; merge session branch to default when ready |
| Design Studios | `C:\Users\kas41\chromatic-design-studios` | `kas1987/chromatic-design-studios` | `master` (+ session branch) | Design system rig | **Partial** — beads + handoff |
| Claude Powerline | `C:\Users\kas41\claude-powerline` | `Owloops/claude-powerline` | `main` | Vendor statusline | Out of band |
| Zelexdoll theme | `C:\Users\kas41\zelexdoll-theme` | *(none)* | `master` | Theme/assets | Out of band |
| Global agents hub | `C:\Users\kas41\.agents` | *(none)* | — | Cross-rig learnings | **Fixed** — `.git` removed; plain directory hub |
| User home | `C:\Users\kas41` | *(removed 2026-05-30)* | — | Was accidental git root | **Fixed** — `.git` → `.git.home-removed-20260530` |

**Submodule (correct):** `chromatic-harness-v2/02_RUNTIME/runtime-engines/roach-pi` → `tmdgusya/roach-pi`

**Nested vendored:** `council-of-nine-tts/{tortoise-tts,TTS}`

---

## Tier 2 — GitHub (`kas1987`) — 29 repos

Run `gh repo list kas1987 --limit 200` for live list. Only these are cloned under `C:\Users\kas41\` today:

| GitHub | Local path |
|--------|------------|
| `chromatic-harness-v2` | `chromatic-harness-v2` |
| `fusion-computer` | `fusion-computer` |
| `claude-config` | `.claude` |
| `claude-powerline` | `claude-powerline` |

### Families (cloud-only unless cloned)

| Family | Repos |
|--------|-------|
| Harness / agent ops | `agentops`, `ai-project-management-harness`, `prism-autonomy-harness`, `ComftyUI-Harness`, `chromatic-devsecops` |
| Chromatic platform | `ChromaticSystems`, `Chromatic_Brain`, `Chromatic_Skills`, `Command-Center`, `-Chromatic_Wiki` |
| Claude toolchain | `claude-skills`, `claude-octopus`, `Claude_Master` |
| Prism / image | `04-Prism`, `04-prism-LAP`, `Image-Prism`, `Image-Org` |
| Creative | `The-Veil`, `Viel-Small-Town`, `3D_Meta` |
| Routing | `9router`, `dmx` |
| Legacy | `CCP`, `JOB`, `Master_CCC` |

---

## Tier 3 — Non-git workspaces

| Path | Purpose |
|------|---------|
| `10_RUNTIME` | Runtime assets |
| `multica_workspaces` | Multica agent workspaces |
| `openhands-workspace` | OpenHands |
| `system-monitor`, `MyPythonGame`, `Moon` | Small apps |

---

## Canonical layout (target)

```text
C:\Users\kas41\
  chromatic-harness-v2\      # beads, handoffs, CI, router
  fusion-computer\           # templates rig
  chromatic-stack\           # docker compose stack
  chromatic-design-studios\  # design system rig
  .claude\                   # clone of claude-config
  .agents\                   # global learnings hub (NOT a git repo)
```

---

## Repo hygiene beads (completed 2026-05-30)

| ID | Status | Title |
|----|--------|-------|
| `chromatic-harness-v2-j9o` | closed | Remove git repo from user home directory |
| `chromatic-harness-v2-p2f` | closed | Create GitHub remotes for stack + design-studios |
| `chromatic-harness-v2-qd3` | closed | Align fusion-computer and claude-config with session compact |

---

## Commands

```powershell
# Regenerate audit table
powershell -File scripts/audit_local_repos.ps1

# Create missing GitHub repos (after review)
gh repo create kas1987/chromatic-stack --private --source C:\Users\kas41\chromatic-stack --remote origin --push
gh repo create kas1987/chromatic-design-studios --private --source C:\Users\kas41\chromatic-design-studios --remote origin --push

# Harvest from extra rigs into harness hub
python scripts/harvest_rigs.py --roots C:\Users\kas41\fusion-computer,C:\Users\kas41\chromatic-design-studios
```
