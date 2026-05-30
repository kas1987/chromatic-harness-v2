---
id: research-2026-05-25-harness-template-multi-repo
type: research
date: 2026-05-25
---

# Research: Config Repo as Canonical Harness Template — Multi-Repo Instantiation Pattern

## Context

The user's mental model: `~/.claude` (kas1987/claude-config) is the **base class**.
Each project repo gets a thin **overlay** — inheriting all global defaults, only overriding what differs.
The pattern is "template + tweak," never "fork and diverge."

## What Exists Today

### Global harness (`~/.claude` = kas1987/claude-config)
- **Skills:** 82 skills in `~/.claude/skills/` (read-only, shared)
- **Hooks:** SessionStart, PreToolUse, PostToolUse chains in `~/.claude/hooks/`
- **MCPs:** review-daemon, director-mcp, whisper-flow-mcp (all live here)
- **Governance:** `governance/multi-router-matrix.yaml`, `governance/auto-mode-scope.yaml`
- **Bootstrap:** `bin/install.sh` — idempotent, cross-platform, clones+builds+configures
- **Federation:** `pnpm run governance:*:federate` copies governance YAMLs to federation_roots

### Missing: Per-Repo Overlay Pattern
- No repos have a `.claude/` overlay today (checked `C:/.04_Prism`, `fusion-computer`)
- `settings.json` is global — no per-repo hook config override
- review-daemon has zero per-repo config support — all hardcoded or env vars
- No `harness-init` script for bootstrapping new repo overlays

## Key Mechanisms Claude Code Provides (Free)

1. **CLAUDE.md inheritance** — Claude Code reads all CLAUDE.md files from cwd upward. A repo's `CLAUDE.md` automatically stacks on `~/.claude/CLAUDE.md`. Zero tooling needed.
2. **Per-project `.mcp.json`** — Claude Code reads `.mcp.json` in the project root; can declare project-specific MCP config that augments global `~/.claude.json`.
3. **Env var overrides** — all review-daemon behaviors already accept env vars; per-repo `.env` or CI secrets can customize without forking.

## The Three Layers

```
Layer 0 — Claude Code global (~/.claude/)
  CLAUDE.md            hard directives (auto-mode, constraints, model routing)
  hooks/               shared hooks (model-router, pre-commit, multica-notify)
  settings.json        global MCP registrations + env vars
  review-daemon/       canonical MCP binary (one instance, shared)
  skills/              82 shared skills (read-only)
  governance/          federated policy YAMLs

Layer 1 — Per-repo overlay (<repo>/.claude/)
  CLAUDE.md            repo-specific directives (stack on global)
  review-daemon.json   overrides: T3 model, extra checks, delivery dir, blocked branches
  hooks/               repo-specific hooks (run after global hooks)

Layer 2 — CI / environment
  .env / secrets       provider keys, OLLAMA_URL, model overrides
  .github/workflows/   CI that invokes review-daemon
```

## What Needs to Be Built

### 1. Review-daemon config file support (review-daemon.json)
review-daemon currently has no per-repo config. It reads from env vars only.
Add: read `.claude/review-daemon.json` from CWD at startup. This file can override:
- `t3_featherless_model` — repo-specific model (e.g., code-heavy repo uses Qwen Coder 32B)
- `t3_ollama_model` — local model override
- `t3_ollama_url` — remote Ollama for teams
- `extra_mechanical_checks` — additional shell commands to run (e.g., `pytest --co`, `eslint --dry-run`)
- `blocked_branches` — add more than the default main/master list
- `delivery_dir` — write deliveries to a repo-specific path

### 2. harness-init script (bin/harness-init.sh)
Given a target repo path:
- Creates `<repo>/.claude/` directory
- Writes `CLAUDE.md` stub (inherits global + adds repo-specific section)
- Writes `review-daemon.json` with all defaults documented
- Optionally adds `.github/workflows/review-daemon.yml` symlink or copy
- Adds repo to governance/auto-mode-scope.yaml federation_roots

### 3. SOP documentation (docs/harness-template-guide.md)
Documents:
- The three-layer model
- What to put in each layer
- How to customize without forking
- Governance federation process for adding new repos
- review-daemon.json schema

## Applicable Test Levels

- **L0** (file existence): harness-init output files must exist
- **L1** (unit): review-daemon config loading — env var vs. file precedence
- **L2** (integration): harness-init → review-daemon reads config from new overlay
