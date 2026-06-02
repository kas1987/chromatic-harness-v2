# Playbook Evolution Feedback Loop

> Bead: `chromatic-harness-v2-7d2.5` · Gap doc: `docs/research/CHROMATIC_HARNESS_V2_GAPS_AND_ECOSYSTEM_LANDSCAPE.md` (P3 #12)

Closes the loop from the **Decision Log** back into the static playbooks under
`04_PLAYBOOKS/`. Previously the playbooks were write-once docs with no mechanism
to learn from what the harness actually decided at runtime. This adds the
missing feedback arrow: *runtime decisions → recurring-pattern proposals →
human-reviewed playbook edits*.

## What it does

`scripts/propose_playbook_evolution.py` reads
`07_LOGS_AND_AUDIT/decisions/decision_log.jsonl` (written by
`02_RUNTIME/audit/two_log.py::append_decision`) and mines three families of
recurring signal, each routed to the most relevant playbook:

| Signal | Trigger | Proposal kind |
|---|---|---|
| Recurring `lesson` text | same lesson ≥ threshold | `codify_lesson` |
| Low/medium-band escalations | `(band, action)` ≥ threshold | `tune_gate` |
| Recurring failure `reason` | clustered reason ≥ threshold | `add_fix_pattern` |

Routine-navigation reasons (`bd show …`, `git …`, `gh …`) are filtered out so
fix-pattern proposals reflect genuine failures, not inspection commands.

## Read-only — human gate required

Per global policy, **background learning systems never auto-edit**. This script
only *proposes*. It writes to a staging area and stops:

- `00_META/observability/PLAYBOOK_EVOLUTION_PROPOSALS.md` — human-readable.
- `00_META/observability/playbook_evolution_proposals.jsonl` — machine-readable.

A maintainer reviews the staging file and manually applies any worthwhile change
to the target playbook. No playbook is ever modified by this script.

## Usage

```bash
# Preview proposals without writing anything:
python scripts/propose_playbook_evolution.py --dry-run

# Append proposals to the staging files (default: last 5000 decisions, threshold 3):
python scripts/propose_playbook_evolution.py

# Tune sensitivity:
python scripts/propose_playbook_evolution.py --threshold 5 --window 20000
```

Run it periodically (e.g. at session end or post-epic) to keep the playbooks
converging on what the harness actually learns in production.
