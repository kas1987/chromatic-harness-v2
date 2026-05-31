# KPI Scorecard — chromatic-harness-v2
Baseline date: 2026-05-31
Next review: 2026-06-07

| KPI | Baseline | Target | Current |
|-----|---------|--------|---------|
| % sessions started from state files | 0% | 80% | 0% |
| % tasks classified P1-P4 | 100% | 100% | 100% |
| % P4 items parked (not worked) | N/A | 95% | N/A |
| % actions logged to decision log | 2 entries | 90% | 2 entries |
| Scope drift incidents / session | 0 | <1 | 0 |
| Broken governance files | 0 | 0 | 0 |

## Notes — measurement methodology

**% sessions started from state files**
`01_STATE/SPRINT_STATE.md` did not exist before this session (xacy.1 created it).
Baseline = 0%. Target clock starts after this commit.

**% tasks classified P1-P4**
`bd list --limit 0` returned 28 total beads; all carry a `● P[0-3]` label (counts:
P0×1, P1×8, P2×13, P3×10). Zero unclassified beads. Baseline = 100%.

**% P4 items parked (not worked)**
No P4-priority beads exist in the tracker. Metric is N/A at baseline.
Will become measurable once P4 beads are created (xacy.3 intent).

**% actions logged to decision log**
`01_STATE/DECISION_LOG.md` was created this session with 2 seed entries.
Baseline = 2 cumulative logged decisions. Target is a % rate per session (to be
trended from xacy.4 onward).

**Scope drift incidents / session**
Last 5 commits reviewed (`git log --oneline -5`): all map to tracked epics
(wip/desktop-rebuild, ci fix, bdbranch feature, hooks refactor, session close-out).
No off-epic work detected. Baseline = 0.

**Broken governance files**
Checked: `AGENT_OPERATIONS.md`, `CLAUDE.md`, `.claude/settings.json` — all present
and non-empty. Baseline = 0 broken files.
