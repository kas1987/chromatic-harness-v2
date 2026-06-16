# Knowledge Flywheel Health

**Date:** 2026-04-05

## Pool Depths
| Pool | Count | Recent (7d) |
|------|-------|-------------|
| Learnings | 4 | 4 |
| Patterns | 0 | 0 |
| Research | 0 | 0 |
| Retros | 0 | 0 |

## Auxiliary Pools
| Pool | Count | Recent (7d) |
|------|-------|-------------|
| Forge | 0 | 0 |
| Knowledge | 0 | 0 |

## Velocity (Last 7 Days)
- Sessions with extractions: 4 (proxy: recent learnings)
- New learnings: 4
- New patterns: 0

## Artifact Consistency
- References scanned: 0
- Broken references: unavailable
- Consistency score: unavailable
- Status: Warning

`scripts/artifact-consistency.sh` was not present in this repo, so cross-reference validation could not run.

## Cache Health
- Hit rate: unavailable
- Uncited learnings: unavailable
- Stale (90d uncited): unavailable
- Status: Warning

`ao` is installed, but it did not return usable flywheel or citation metrics here. Local `.agents/ao` telemetry files are also absent.

## Health Status
Warning

The loop is active at the learning-capture layer, but there is no evidence yet of promotion, citation, or research closure. This repo is collecting knowledge, not compounding it.

## Friction Points
- The flywheel is concentrated in one pool: four learnings, zero patterns, zero research, and zero retros.
- Cache and citation signals are unavailable because `.agents/ao` data is missing and `ao` did not emit usable status output.
- Artifact consistency validation is not wired in because the documented consistency script is absent.
- The underlying Gen observability data model is incomplete in the live database, so downstream knowledge and usage reporting undercounts reality.

## Recommendations
1. Backfill the live Gen migrations so `routing_decisions` exists and `task_outcomes` includes provider and intent columns.
2. Start emitting or retaining `.agents/ao` citation, outcome, and skill telemetry so cache health can be measured instead of inferred.
3. Add an artifact consistency script for this repo or document an alternative validation path.
4. Convert the current run into at least one retro and one pattern if the same observability issue recurs again.