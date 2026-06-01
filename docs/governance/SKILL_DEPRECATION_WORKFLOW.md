# Skill Deprecation Workflow

> **Inventory tool:** `python scripts/skill_inventory.py`
> **See also:** [docs/governance/GOVERNANCE_EXPANSION_GATE.md](GOVERNANCE_EXPANSION_GATE.md)

## Purpose

Track skill usage, identify overlaps and retirement candidates, and provide a
reproducible process for safely retiring skills without breaking active workflows.

---

## Skill Inventory

Skills live in these roots (scanned in priority order):

| Root | Notes |
|---|---|
| `<repo>/.claude/skills/` | Project-scoped skills |
| `~/.claude/skills/` | User-global skills |
| `~/.agents/skills/` | Agent team skills |
| `<repo>/.claude/plugins/` | Plugin-wrapped skills |
| `~/.claude/plugins/` | Global plugin skills |

Generate the current inventory:

```bash
python scripts/skill_inventory.py
python scripts/skill_inventory.py --json > .agents/harvest/skill_inventory.json
```

---

## Deprecation Criteria

A skill is a **deprecation candidate** when ALL of the following are true:

1. **Stale:** Not invoked in the last 30 days (or never invoked).
2. **Low usage:** Total invocation count < 3 across all recorded events.
3. **No active dependency:** No other skill, hook, or workflow imports or
   references the skill by name (checked via grep of `.claude/`, `scripts/`,
   `docs/`, `.agents/`).

Skills that are stale but frequently used historically (count ≥ 3) should be
**reviewed**, not immediately retired.

---

## Deprecation Process

### Step 1 — Identify candidates

```bash
python scripts/skill_inventory.py --deprecation-candidates
```

Review the output. For each candidate:
- Check the skill path and doc.
- Search for references: `grep -r "<skill-name>" .claude/ scripts/ docs/ .agents/`
- Confirm no active bead, workflow, or CI step depends on it.

### Step 2 — Create a review bead

```bash
bd add --title "Deprecate skill: <name>" \
       --body "Candidate identified by skill_inventory. Last used: <date>. Invocations: N. Path: <path>." \
       --label deprecation --priority p2
```

### Step 3 — Move to archive (not delete)

```bash
# Project skill
mv .claude/skills/<name>/ .claude/skills/_archived/<name>-deprecated-$(date +%Y%m%d)/

# Global skill
mv ~/.claude/skills/<name>/ ~/.claude/skills/_archived/<name>-deprecated-$(date +%Y%m%d)/
```

Do **not** hard-delete — archive for 30 days in case a workflow resurfaces a dependency.

### Step 4 — Update inventory and knowledge

```bash
python scripts/skill_inventory.py --json > .agents/harvest/skill_inventory.json
bd remember "Deprecated skill <name> on $(date +%Y-%m-%d). Path archived at .claude/skills/_archived/."
```

### Step 5 — Hard delete (after 30-day hold)

After 30 days with no reactivation:
```bash
rm -rf .claude/skills/_archived/<name>-deprecated-*/
```

Close the review bead:
```bash
bd close <bead-id> --note "30-day hold elapsed; hard deleted."
```

---

## Overlap Detection

When two skills appear to do the same thing:

1. Run inventory and compare doc files manually.
2. Check invocation counts — keep the higher-usage one.
3. If equal, prefer the one in the higher-priority root (repo > global > agents).
4. Create a redirect stub in the retired skill's path pointing to the survivor:

```markdown
# <retired-name> — Deprecated

This skill has been merged into [<survivor>](<path>).
Use `/<survivor>` instead.
```

---

## Utilization Tracking

Invocation data is read from `.agents/chronicle/events.jsonl`. The chronicle
records skill invocations when:

- A `/skill-name` slash command is executed in Claude Code.
- A pipeline skill (`/crank`, `/rpi`, etc.) emits a `skill_invoked` event.
- The harness hooks log a skill execution.

To emit a skill event manually (e.g., from a custom skill):

```python
import json, time, pathlib
record = {
    "event": "skill_invoked",
    "skill": "<skill-name>",
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "source": "manual",
}
p = pathlib.Path(".agents/chronicle/events.jsonl")
with p.open("a") as f:
    f.write(json.dumps(record) + "\n")
```

---

## Dashboard Integration

The inventory tool outputs a JSON blob compatible with the harness health dashboard:

```bash
python scripts/skill_inventory.py --json
```

Key fields in the output:
- `summary.total_skills` — total discovered
- `summary.deprecation_candidates` — ready for review
- `skills[].invocation_count` — from chronicle
- `skills[].last_used_iso` — last recorded invocation
- `skills[].deprecation_candidate` — boolean flag

Pipe to dashboard: add the JSON output to `07_LOGS_AND_AUDIT/harness_health/` as
`skill_inventory_latest.json` for pickup by the health dashboard.

---

## CI Check

Add to pre-push or weekly CI:

```bash
python scripts/skill_inventory.py --json | \
  python -c "import sys,json; d=json.load(sys.stdin); \
  cands=d['summary']['deprecation_candidates']; \
  print(f'Deprecation candidates: {cands}'); \
  sys.exit(1 if cands > 20 else 0)"
```

Fail if more than 20 deprecation candidates accumulate without review.
