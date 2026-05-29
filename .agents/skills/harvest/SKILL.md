---
name: harvest
description: >
  Cross-rig knowledge consolidation. One-time sweep + ongoing tiered promotion.
  Walks all .agents/ directories, extracts learnings/patterns/research,
  deduplicates across rigs, and promotes high-value items to global hub.
  Triggers: "harvest", "consolidate knowledge", "cross-rig sweep",
  "knowledge federation", "harvest knowledge".
skill_api_version: 1
user-invocable: true
context:
  window: fork
  intent:
    mode: task
metadata:
  tier: knowledge
  dependencies: []
---

# Harvest — Cross-Rig Knowledge Consolidation

Sweep all `.agents/` directories across the workspace, extract learnings, patterns,
and research, deduplicate cross-rig, and promote high-value items to the global
knowledge hub (`~/.agents/learnings/`).

## What This Skill Does

The knowledge flywheel captures learnings per-rig, but they stay siloed. Harvest
closes the loop by walking all rigs, extracting artifacts, deduplicating by content
hash, and promoting high-confidence items to the global hub where every rig can
access them via `ao inject`.

**When to use:** Before an evolve cycle, after a burst of development across
multiple rigs, or weekly as part of knowledge governance.

**Output:** `.agents/harvest/latest.json` (catalog) + promoted files in `~/.agents/learnings/`

## Execution Steps

> **Implementation note:** This skill drives the harvest workflow from inside Claude using the `ao forge` + `ao extract` primitives plus a manual promotion step. There is no `ao harvest` subcommand — it has been retired from the design (see `~/.agents/learnings/2026-05-21-ao-harvest-not-exists.md`). Do not look for one.

### Step 1: Extract from Recent Sessions

```bash
# For each recent session transcript:
ao forge transcript <session.jsonl> --queue --quiet
# Then bulk extract:
ao extract --all
```

Read the resulting queued items in `~/.agents/learnings/` and `.agents/learnings/` and report:
- Sessions processed
- Total artifacts extracted
- Unique vs duplicate count (run `ao dedup --merge` to assess)
- Promotion candidates (artifacts with confidence >= 0.5 from frontmatter)

### Step 2: Log and Proceed (Autonomous)

Default behavior: log the extraction summary (`"Forge produced N artifacts from M sessions; M unique, K candidates for promotion."`) and proceed directly to Step 3. Only if `--review` flag is set, surface the summary and ask:

```
Harvest will promote N artifacts from M rigs to ~/.agents/learnings/.
Proceed? [Approve / Adjust threshold / Abort]
```

### Step 3: Promote Manually

Promotion is hand-driven (or shell-scripted) — there is no auto-promote subcommand. For each candidate:

```bash
# Inspect, then move to global hub:
cp .agents/learnings/<file>.md ~/.agents/learnings/
```

Ensure each promoted file has proper frontmatter (`name`, `description`, `tier`, `confidence`).

### Step 4: Post-Harvest Cleanup

Run dedup on the promotion target to clean up any remaining duplicates:

```bash
ao dedup --merge ~/.agents/learnings/ 2>/dev/null || true
```

### Step 5: Report Results

Report to user:
- Rigs scanned
- Artifacts extracted and unique count
- Duplicates found (with top duplicate groups)
- Artifacts promoted (with provenance)
- Top discoveries (highest-confidence cross-rig patterns)

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--auto` | off | Skip confirmation gate |
| `--roots` | `~/gt/` | Override root directories to scan |
| `--min-confidence` | 0.5 | Minimum confidence for promotion |
| `--include` | `learnings,patterns,research` | Artifact types to extract |

## Quick Start

```bash
/harvest                          # Full sweep with confirmation
/harvest --auto                   # Hands-free sweep
/harvest --min-confidence 0.7     # Only promote high-confidence items
/harvest --roots ~/gt/,~/projects/ # Scan additional directories
```

## Governance

See [references/governance.md](references/governance.md) for ongoing governance model:
size budgets, sweep frequency, staleness thresholds, and cross-rig synthesis triggers.

## See Also

- [skills/athena/SKILL.md](../athena/SKILL.md) — Single-rig Mine/Grow/Defrag
- [skills/flywheel/SKILL.md](../flywheel/SKILL.md) — Flywheel health monitoring
- [skills/inject/SKILL.md](../inject/SKILL.md) — Knowledge injection into sessions
- [skills/forge/SKILL.md](../forge/SKILL.md) — Transcript knowledge extraction

## Reference Documents

- [references/governance.md](references/governance.md) — Governance model for ongoing knowledge consolidation

## Examples

### Full sweep with confirmation
```
/harvest
```
Expected: Scans all configured roots, presents candidates for promotion, asks confirmation before writing to knowledge base.

### Hands-free sweep
```
/harvest --auto
```
Expected: Promotes all items above default confidence threshold without prompting. Runs silently.

### High-confidence only
```
/harvest --min-confidence 0.7
```
Expected: Only items with ≥70% confidence score are promoted; borderline items are skipped.

### Scan additional directories
```
/harvest --roots ~/gt/,~/projects/
```
Expected: Scans both additional roots alongside default scan paths.

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| No items found | Scan roots empty or misconfigured | Verify `--roots` paths exist; run without `--roots` first to confirm defaults work |
| Duplicates promoted | Same item in multiple roots | Check governance.md for deduplication rules; run `/athena defrag` after harvest |
| Confidence scores all low | Shallow learnings with no cross-referencing | Write richer retro notes; run `/forge` first to extract more structured learnings |
| `--auto` promotes bad items | Confidence threshold too low | Raise to `--min-confidence 0.8`; review governance.md staleness thresholds |
| Knowledge base size exceeded | Too many promotions without cleanup | Run `/flywheel` health check; trim via governance size budget policy |
