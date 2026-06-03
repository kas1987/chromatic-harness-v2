# GitKraken integration (gk CLI + MCP)

Harness git automations use **GitKraken CLI** when installed (`CHROMATIC_GIT_BACKEND=auto`, default).

## Install

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_dev_clis.ps1
gk auth login
```

Optional (AI commit/PR): `gk organization set <org>` on a paid GitKraken plan.

## Pipeline backend

| Backend | Behavior |
|---------|----------|
| `auto` | `gk` for git ops if `gk version` succeeds; else `git` |
| `gk` | Force `gk` passthrough (`gk commit`, `gk push`, …) |
| `git` | Native `git` only |

```bash
python scripts/workflow_git.py plan --confidence 90 --verifier approve --tests-passed --backend auto
python scripts/workflow_git.py ship --execute --from-log --verifier approve --tests-passed --backend gk
```

PR open/merge still uses **`gh`** (GitHub CLI). `gk pr` does not replace `gh pr create` in this pipeline.

## Cursor MCP

Project config: [`.cursor/mcp.json`](../../.cursor/mcp.json) — enable **gitkraken** in Cursor MCP settings or run **GitLens: Install GitKraken MCP Server**.

Verify in Agent mode: ask the agent to list assigned PRs (uses GitKraken MCP tools after approval).

## Related

- [GIT_CONFIDENCE_PIPELINE.md](GIT_CONFIDENCE_PIPELINE.md)
- [GIT_AUTONOMY_POLICY.md](../governance/GIT_AUTONOMY_POLICY.md)
- `02_RUNTIME/workflows/git_runner.py`
