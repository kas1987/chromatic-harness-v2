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
    sev=Counter(e.get('severity','unknown') for e in events); cat=Counter(e.get('category','unknown') for e in events); status=Counter(e.get('status','unknown') for e in events); open_events=[e for e in events if e.get('status') in {'open','queued','incident_opened','collision_opened'}]
    out=Path(args.out) if args.out else root/'00_META/observability/reports'/('OBSERVABILITY_REPORT_'+utc_now()[:10]+'.md'); out.parent.mkdir(parents=True, exist_ok=True)
    lines=['# Observability Report','',f'Generated: {utc_now()}','',f'Total events: {len(events)}','','## Severity Counts','']+[f'- {k}: {v}' for k,v in sev.most_common()]+['','## Category Counts','']+[f'- {k}: {v}' for k,v in cat.most_common()]+['','## Status Counts','']+[f'- {k}: {v}' for k,v in status.most_common()]+['','## Open / Routed Events','']
    for e in open_events[-20:]: lines.append(f"- {e.get('event_id')} | {e.get('severity')} | {e.get('category')} | {e.get('error_signature','')}")
    out.write_text('\n'.join(lines)+'\n', encoding='utf-8'); print(out)
if __name__=='__main__': main()
