# Observability Reports & Learning Candidates (OBS-010)

Turn raw event history into human-readable reports and reviewable learning
candidates.

## `generate_observability_report.py`

Writes a dated markdown report under
`00_META/observability/reports/OBSERVABILITY_REPORT_<YYYY-MM-DD>.md`.

```bash
python scripts/generate_observability_report.py
python scripts/generate_observability_report.py --out /tmp/report.md
```

The report includes:

- **Severity / Category / Latest-Status counts** (all time).
- **Unresolved High / Critical Events** — what needs attention now.
- **Repeated Error Signatures** — signatures seen ≥ 2×.
- **Files Most Often Touched By Events** — noisy files.
- **Open / Routed Events** — the most recent open items.
- **Recommended Next Work** — derived from the above.

Latest status is computed per `event_id` across all records (so a later
`status_update` supersedes the original), and open events are de-duplicated.

## `propose_learnings.py`

Identifies error signatures that recur at or above a threshold and proposes
them as learning candidates.

```bash
# Default: STAGE proposals for review (does NOT touch the canonical log).
python scripts/propose_learnings.py --threshold 3
#   -> 00_META/observability/staging/LEARNING_CANDIDATES_<YYYY-MM-DD>.md

# Gated promotion to the canonical learnings log (explicit opt-in).
python scripts/propose_learnings.py --threshold 3 --commit
#   -> appends to 00_META/observability/LEARNINGS_LOG.md
```

### Governance: proposals are staged, not auto-applied

By design this is a **read-only analysis** tool. It never mutates the canonical
`LEARNINGS_LOG.md` unless you pass `--commit`. The default path writes a clearly
labelled *PROPOSED* candidates file to a `staging/` directory, so a human (or a
review gate) decides what becomes a durable learning. This mirrors the harness
rule that background learning systems must stage proposals behind an explicit
gate rather than self-modify project knowledge.

## Suggested cadence

Run both on a schedule (e.g. daily or per-session-close) and review the staged
candidates before promoting. The report's *Recommended Next Work* section is a
good driver for the next observability work item.
