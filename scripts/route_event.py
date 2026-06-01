#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from common_harness import priority_for,repo_root,utc_now

def load_event(root,event_id):
    path=root/'00_META/observability/ERROR_LOG.jsonl'; found=None
    for line in path.read_text(encoding='utf-8').splitlines() if path.exists() else []:
        if line.strip():
            rec=json.loads(line)
            if rec.get('event_id')==event_id: found=rec
    return found

def append_md(path,text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f: f.write('\n'+text.strip()+'\n')

def main():
    ap=argparse.ArgumentParser(description='Route an event to incident/collision/queue artifacts')
    ap.add_argument('--repo-root'); ap.add_argument('--event-id', required=True)
    args=ap.parse_args(); root=Path(args.repo_root).resolve() if args.repo_root else repo_root(); ev=load_event(root,args.event_id)
    if not ev: print(f'event not found: {args.event_id}', file=sys.stderr); return 2
    sev=ev.get('severity','info'); cat=ev.get('category','unknown'); routed=[]
    if sev=='critical' or cat in {'secret_exposure','scope_breach','loop_behavior'}:
        incident=("## Incident: {event_id}\n\n| Field | Value |\n|---|---|\n| Timestamp | {ts} |\n| Severity | {sev} |\n| Category | {cat} |\n| Source | {source} |\n| Status | open |\n\n### Summary\n{summary}\n\n### Required Action\nHuman or auditor review required before further mutation if this affects repo state, secrets, or destructive operations.\n").format(event_id=ev['event_id'], ts=utc_now(), sev=sev, cat=cat, source=ev.get('source',{}).get('surface','unknown'), summary=(ev.get('raw_excerpt','')[:1000] or ev.get('error_signature','No excerpt provided.')))
        append_md(root/'00_META/observability/INCIDENT_LOG.md', incident); routed.append('incident')
    if cat=='file_collision':
        files=', '.join(ev.get('files_touched',[])) or 'unknown'
        collision=("## Collision: {event_id}\n\n| Field | Value |\n|---|---|\n| Timestamp | {ts} |\n| Severity | {sev} |\n| Files | {files} |\n| Status | open |\n\n### Evidence\n{evidence}\n\n### Resolution Rule\nStop writes to affected files, snapshot versions, and assign a single resolver.\n").format(event_id=ev['event_id'], ts=utc_now(), sev=sev, files=files, evidence=(ev.get('raw_excerpt','')[:1000] or ev.get('error_signature','Collision event routed.')))
        append_md(root/'00_META/observability/COLLISION_REGISTER.md', collision); routed.append('collision')
    if sev in {'medium','high','critical'}:
        pri=priority_for(sev,cat); task=f"Investigate and resolve {cat} from {ev['event_id']}"
        append_md(root/'00_META/queues/ERROR_REMEDIATION_QUEUE.md', f"| ERR-{ev['event_id']} | pending | {pri} | {ev['event_id']} | {cat} | {sev} | Auditor/Codex | {task} | Event is resolved, validation passes, and fix/learning is linked. |")
        routed.append('queue')
    print('routed: '+(', '.join(routed) if routed else 'no route required')); return 0
if __name__=='__main__': raise SystemExit(main())
