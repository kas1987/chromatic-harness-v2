# Cursor User Rules snippet

Copy sections below into **Cursor Settings → Rules → User Rules** (replace old git-only-on-ask blocks).

---

## Git (tiered autonomy)

For **chromatic-harness-v2** and any repo with `scripts/workflow_git.py`:

- Run `python scripts/workflow_git.py plan` before commit/push; use `ship --execute` only when the plan allows each step.
- **Do not** wait for a separate "please commit" or "please push" when gates pass:
  - Commit: confidence ≥ 75, risk not critical, verifier approve
  - Push: confidence ≥ 88, tests passed, risk not high/critical
  - Merge: confidence ≥ 95, CI green, low risk only
- Policy: repo `docs/governance/GIT_AUTONOMY_POLICY.md`

For other repos: commit when implementation is complete or user asked; push when user asked or PR workflow requires it after tests pass.

**Never** without explicit user request: force-push main/master, `git reset --hard`, skip hooks (`--no-verify`), commit secrets (`.env`, keys).

---

## Harness work (chromatic-harness-v2)

- Start: [AGENT_OPERATIONS.md](AGENT_OPERATIONS.md), `bd ready`, handoff pointer.
- Track work in **beads** (`bd`), not TodoWrite or chat TODO lists.
- Use lite workflows; do not chain `/crank` unattended.
- **MCP hygiene (manual):** Cursor Settings → MCP — keep harness_dev lean; disable Resend, Playwright, Opsera unless the task needs them ([docs/CURSOR_CONTEXT_HYGIENE.md](../../docs/CURSOR_CONTEXT_HYGIENE.md)).
- Session end: tests → `workflow_git.py plan` → push if allowed → `bd dolt push` → handoff.

---

## Commits and PRs (general)

- Create commits when work is complete and gates pass, or when the user explicitly asks.
- Use conventional commit messages; never amend pushed commits unless user asks.
- Use `gh` for GitHub PRs; do not push unless gates pass or user asks (harness repos: gates define "ask").

---

## Communication

- Prefer code citations `startLine:endLine:path` for navigation.
- Proportional responses; no engagement baiting.
