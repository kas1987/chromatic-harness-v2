# Knowledge Harvest (`harvest_rigs.py`)

Session-end and on-demand promotion of learnings, patterns, and research from rig `.agents/` trees into the repo knowledge hub.

## When to run

| Trigger | Command |
|---------|---------|
| Session compact / handoff | Automatic via `write_handoff()` |
| Manual dry-run | `python scripts/harvest_rigs.py` |
| Promote + catalog | `python scripts/harvest_rigs.py --execute` |
| Cross-rig sweep | `python scripts/harvest_rigs.py --roots ~/gt/other-rig --execute` |
| Global hub (optional) | `python scripts/harvest_rigs.py --execute --global-hub` |

## After long-running agent batches

After any high-duration autonomous run (loops/swarms/background agents), run:

```bash
python scripts/harvest_rigs.py --execute
python scripts/promote_to_wiki.py --dry-run
python scripts/promote_to_wiki.py --execute
```

This ensures real-world incidents (command failures, telemetry gaps, reroute behaviors) are retained beyond ephemeral session output.

## Behavior

1. Discover rigs with `.agents/{learnings,patterns,research}/`
2. Parse markdown frontmatter (`confidence`, `name`)
3. Dedupe by normalized body SHA256 (keep highest confidence)
4. Promote artifacts with `confidence >= threshold` to `.agents/learnings/`
5. Write catalog `.agents/harvest/latest.json` on `--execute`

## Defaults

- **Dry-run** unless `--execute`
- **Session-end** uses `min_confidence=0.6`, repo hub only
- **Full harvest** default `min_confidence=0.5`

See also: [.agents/skills/harvest/SKILL.md](../.agents/skills/harvest/SKILL.md) for interactive `/harvest` workflow.
