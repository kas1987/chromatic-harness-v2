#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path
from collections import Counter
from common_harness import repo_root,utc_now

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root'); ap.add_argument('--out'); args=ap.parse_args(); root=Path(args.repo_root).resolve() if args.repo_root else repo_root(); log=root/'00_META/observability/ERROR_LOG.jsonl'; events=[]
    if log.exists():
        for line in log.read_text(encoding='utf-8').splitlines():
            if line.strip():
                try: events.append(json.loads(line))
                except Exception: pass
    sev=Counter(e.get('severity','unknown') for e in events); cat=Counter(e.get('category','unknown') for e in events)
    # Compute latest status per event_id from all events (including status_update)
    from collections import defaultdict
    events_by_id = defaultdict(list)
    for e in events:
        eid = e.get('event_id')
        if eid:
            events_by_id[eid].append(e)
    latest_status = {}
    for eid, evts in events_by_id.items():
        # Sort by timestamp descending and take the most recent status
        evts_sorted = sorted(evts, key=lambda x: x.get('timestamp',''), reverse=True)
        latest_status[eid] = evts_sorted[0].get('status','unknown')
    status_counts = Counter(latest_status.values())
    open_statuses = {'open','queued','incident_opened','collision_opened','active','routed'}
    open_events = [e for e in events if e.get('event_id') in latest_status and latest_status[e.get('event_id')] in open_statuses]
    # Deduplicate open events to show the latest record per event_id
    seen_open = set()
    deduped_open = []
    for e in sorted(events, key=lambda x: x.get('timestamp',''), reverse=True):
        eid = e.get('event_id')
        if eid and latest_status.get(eid) in open_statuses and eid not in seen_open:
            seen_open.add(eid)
            deduped_open.append(e)
    open_events = list(reversed(deduped_open))  # chronological

    # Repeated signatures
    sig_counts = Counter(e.get('error_signature') or e.get('category','unknown') for e in events if e.get('error_signature'))
    repeated_sigs = [(s, c) for s, c in sig_counts.most_common() if c >= 2]

    # Noisy files
    files_counter = Counter()
    for e in events:
        for f in e.get('files_touched') or []:
            files_counter[f] += 1
    noisy_files = files_counter.most_common(10)

    # High/critical unresolved
    high_critical_open = [e for e in open_events if e.get('severity') in {'high','critical'}]

    out=Path(args.out) if args.out else root/'00_META/observability/reports'/('OBSERVABILITY_REPORT_'+utc_now()[:10]+'.md'); out.parent.mkdir(parents=True, exist_ok=True)
    lines=['# Observability Report','',f'Generated: {utc_now()}','',f'Total events: {len(events)}','','## Severity Counts (all time)','']+[f'- {k}: {v}' for k,v in sev.most_common()]+['','## Category Counts (all time)','']+[f'- {k}: {v}' for k,v in cat.most_common()]+['','## Latest Status Counts','']+[f'- {k}: {v}' for k,v in status_counts.most_common()]

    # High/Critical Unresolved
    lines += ['','## Unresolved High / Critical Events','']
    if high_critical_open:
        for e in high_critical_open:
            lines.append(f"- {e.get('event_id')} | {e.get('severity')} | {e.get('category')} | {e.get('error_signature','')}")
    else:
        lines.append('- None')

    # Repeated Signatures
    lines += ['','## Repeated Error Signatures','']
    if repeated_sigs:
        for sig, count in repeated_sigs:
            lines.append(f'- {count}x: `{sig}`')
    else:
        lines.append('- None')

    # Noisy Files
    lines += ['','## Files Most Often Touched By Events','']
    if noisy_files:
        for fpath, count in noisy_files:
            lines.append(f'- {count}x: `{fpath}`')
    else:
        lines.append('- None')

    # Open / Routed Events
    lines += ['','## Open / Routed Events','']
    for e in open_events[-20:]:
        lines.append(f"- {e.get('event_id')} | {e.get('severity')} | {e.get('category')} | {e.get('error_signature','')}")

    # Recommended Next Work
    lines += ['','## Recommended Next Work','']
    recs = []
    if high_critical_open:
        recs.append(f'- Resolve {len(high_critical_open)} high/critical open event(s)')
    if repeated_sigs:
        recs.append(f'- Investigate repeated signature(s): {", ".join(f"`{s}`" for s, c in repeated_sigs[:3])}')
    if noisy_files:
        recs.append(f'- Review noisy file(s): {", ".join(f"`{f}`" for f, c in noisy_files[:3])}')
    if not recs:
        recs.append('- No recommended work; observability is clean.')
    lines += recs
    lines.append('')

    out.write_text('\n'.join(lines), encoding='utf-8'); print(out)
if __name__=='__main__': main()
