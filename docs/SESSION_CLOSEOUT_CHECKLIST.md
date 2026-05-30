# Session Close-Out Checklist

> **Authority:** Combines [12_HANDOFFS/SESSION_COMPACT.md](../12_HANDOFFS/SESSION_COMPACT.md) (compact) + [AGENTS.md](../AGENTS.md) (session completion) + lite workflows.

Use at **~65% context**, **phase boundaries**, or **end of long Cursor chats**.

## One command (preferred)

```bash
python scripts/session_closeout.py --invoked-by cursor
```

Optional flags: `--harvest`, `--wiki-dry-run`, `--git-triage`, `--pytest`, `--spawn-successor` (with `CHROMATIC_AUTO_SPAWN=1` when budget allows).

Outputs: `.agents/handoffs/transfer_packet.json`, `.agents/handoffs/closeout_telemetry_latest.json`, `successor_prompt.md`, `latest.json`, markdown under `12_HANDOFFS/sessions/`.

Policy: [governance/AGENT_TRANSFER_POLICY.md](governance/AGENT_TRANSFER_POLICY.md).

---

## 1. Freeze snapshot

```bash
git branch --show-current
git status --short
git log -3 --oneline
bd ready
pytest tests/ -q          # if code changed this session
```

---

## 2. Ingest completed work

| Step | Command / action |
|------|------------------|
| Close finished beads | `bd close <id> --reason "..."` |
| File follow-up beads | `bd create "..." --type task --priority p2` |
| Activity log | `python scripts/log_agent_activity.py log --event phase.complete --bead-id <id> --lane agent --summary "..."` |
| Git failures | `python scripts/git_triage.py --from-log` → `python scripts/auto_intake.py --dry-run` |

---

## 3. Learnings and Wiki

```bash
python scripts/harvest_rigs.py --execute
python scripts/promote_to_wiki.py --dry-run
python scripts/sync_wiki_mirror.py --dry-run   # if governance/docs changed
```

Learnings need YAML frontmatter with `confidence: 0.75` minimum for Wiki promotion (see `02_LEARNINGS/_template.md` in Wiki repo).

---

## 4. Risks, challenges, concerns (handoff)

Fill [AGENT_HANDOFF_TEMPLATE.md](../12_HANDOFFS/AGENT_HANDOFF_TEMPLATE.md) → save as:

```text
12_HANDOFFS/sessions/<mission-or-date>.md
```

Update pointer:

```text
.agents/handoffs/latest.json
```

---

## 5. Backlog and routing review

| Check | How |
|-------|-----|
| Open epics | `bd ready` — avoid starting duplicate epics |
| Human vs agent lane | `python scripts/bd_ready_by_lane.py --lane human` |
| Router policy | Open `15x.*` / `gh1` / `uum` only when doing routing work |
| No chat TODOs | All follow-ups in `bd` or intake queue |

---

## 6. Context hygiene

```bash
python scripts/context_trim_audit.py --root .
python scripts/daily_harness_audit.py --root . --report --strict
python scripts/audit_mcp_context.py --profile harness_dev
```

**Manual:** Cursor Settings → Rules — paste [docs/cursor/USER_RULES_SNIPPET.md](cursor/USER_RULES_SNIPPET.md); disable unused MCPs per [CURSOR_CONTEXT_HYGIENE.md](CURSOR_CONTEXT_HYGIENE.md).

Read `.agents/context/BOOT_CONTEXT.md` and `.agents/audits/latest_audit_summary.md` if audit is red/yellow.

---

## 7. Session completion (mandatory when shipping)

Per AGENTS.md:

1. File/close beads for remaining work  
2. Quality gates (pytest, ruff if code changed)  
3. Commit intentional changes (not generated logs)  
4. **`git pull --rebase` && `git push`**  
5. Handoff written (step 4 above)

---

## 8. Effectiveness vs efficacy (60-second review)

| Question | Green if |
|----------|----------|
| Did we close beads we actually finished? | `bd show` matches reality |
| Did we externalize learnings? | harvest or handoff lists them |
| Did we avoid token burn? | MCP audit / antipatterns followed |
| Is next session obvious? | `latest.json` + one `next_command` |

---

## Lite workflow aliases

| User says | Run |
|-----------|-----|
| `/close-issue` | Close bead + optional `workflow_go GO VERIFY` (see `.claude/workflows/`) |
| Hand off / pause | Full checklist (this doc) |
| GO SHIP | `workflow_git.py` with confidence gates only |

---

## Related

- [AGENT_OPERATIONS.md](../AGENT_OPERATIONS.md)
- [docs/governance/ACTIVITY_LOG_AND_DUAL_BACKLOG.md](governance/ACTIVITY_LOG_AND_DUAL_BACKLOG.md)
- [docs/WIKI_REPO_AND_PROMOTION.md](WIKI_REPO_AND_PROMOTION.md)
- [04_PLAYBOOKS/SESSION_COMPACT_PLAYBOOK.md](../04_PLAYBOOKS/SESSION_COMPACT_PLAYBOOK.md)
