#!/usr/bin/env python3
"""generate_observability_report.py — dated markdown report from the event log.

Includes (OBS-010 acceptance): unresolved high/critical events, repeated error
signatures, noisy files, and recommended next work — alongside all-time
severity/category/status counts.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from common_harness import repo_root, utc_now

OPEN_STATUSES = {"open", "queued", "incident_opened", "collision_opened", "active", "routed"}


def load_events(log: Path) -> list[dict]:
    events = []
    if not log.exists():
        return events
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)  # file may be partially written; guard parse
        except (ValueError, TypeError):
            continue
        if isinstance(rec, dict):
            events.append(rec)
    return events


def latest_status_by_id(events: list[dict]) -> dict:
    by_id = defaultdict(list)
    for e in events:
        eid = e.get("event_id")
        if eid:
            by_id[eid].append(e)
    out = {}
    for eid, evts in by_id.items():
        newest = sorted(evts, key=lambda x: x.get("timestamp", ""), reverse=True)[0]
        out[eid] = newest.get("status", "unknown")
    return out


def main():
    ap = argparse.ArgumentParser(description="Generate a dated observability report.")
    ap.add_argument("--repo-root")
    ap.add_argument("--out")
    args = ap.parse_args()
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    events = load_events(root / "00_META/observability/ERROR_LOG.jsonl")

    sev = Counter(e.get("severity", "unknown") for e in events)
    cat = Counter(e.get("category", "unknown") for e in events)
    latest = latest_status_by_id(events)
    status_counts = Counter(latest.values())

    # Deduplicated open events (latest record per id), chronological.
    seen, deduped = set(), []
    for e in sorted(events, key=lambda x: x.get("timestamp", ""), reverse=True):
        eid = e.get("event_id")
        if eid and latest.get(eid) in OPEN_STATUSES and eid not in seen:
            seen.add(eid)
            deduped.append(e)
    open_events = list(reversed(deduped))

    high_critical_open = [e for e in open_events if e.get("severity") in {"high", "critical"}]

    sig_counts = Counter(
        e.get("error_signature") or e.get("category", "unknown") for e in events if e.get("error_signature")
    )
    repeated_sigs = [(s, c) for s, c in sig_counts.most_common() if c >= 2]

    files_counter = Counter()
    for e in events:
        for f in e.get("files_touched") or []:
            files_counter[f] += 1
    noisy_files = files_counter.most_common(10)

    lines = ["# Observability Report", "", f"Generated: {utc_now()}", "", f"Total events: {len(events)}"]
    lines += ["", "## Severity Counts (all time)", ""] + [f"- {k}: {v}" for k, v in sev.most_common()]
    lines += ["", "## Category Counts (all time)", ""] + [f"- {k}: {v}" for k, v in cat.most_common()]
    lines += ["", "## Latest Status Counts", ""] + [f"- {k}: {v}" for k, v in status_counts.most_common()]

    lines += ["", "## Unresolved High / Critical Events", ""]
    if high_critical_open:
        for e in high_critical_open:
            lines.append(
                f"- {e.get('event_id')} | {e.get('severity')} | {e.get('category')} | {e.get('error_signature', '')}"
            )
    else:
        lines.append("- None")

    lines += ["", "## Repeated Error Signatures", ""]
    lines += [f"- {c}x: `{s}`" for s, c in repeated_sigs] or ["- None"]

    lines += ["", "## Files Most Often Touched By Events", ""]
    lines += [f"- {c}x: `{f}`" for f, c in noisy_files] or ["- None"]

    lines += ["", "## Open / Routed Events", ""]
    for e in open_events[-20:]:
        lines.append(
            f"- {e.get('event_id')} | {e.get('severity')} | {e.get('category')} | {e.get('error_signature', '')}"
        )

    lines += ["", "## Recommended Next Work", ""]
    recs = []
    if high_critical_open:
        recs.append(f"- Resolve {len(high_critical_open)} high/critical open event(s)")
    if repeated_sigs:
        joined = ", ".join(f"`{s}`" for s, _ in repeated_sigs[:3])
        recs.append(f"- Investigate repeated signature(s): {joined}")
    if noisy_files:
        joined = ", ".join(f"`{f}`" for f, _ in noisy_files[:3])
        recs.append(f"- Review noisy file(s): {joined}")
    lines += recs or ["- No recommended work; observability is clean."]
    lines.append("")

    out = (
        Path(args.out)
        if args.out
        else root / "00_META/observability/reports" / ("OBSERVABILITY_REPORT_" + utc_now()[:10] + ".md")
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
