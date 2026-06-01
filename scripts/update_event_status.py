#!/usr/bin/env python3
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path
from common_harness import repo_root

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--event-id', required=True); ap.add_argument('--status', required=True); ap.add_argument('--linked-fix', default=''); ap.add_argument('--repo-root'); args=ap.parse_args(); root=Path(args.repo_root).resolve() if args.repo_root else repo_root()
    script_dir = Path(__file__).resolve().parent
    return subprocess.call([sys.executable, str(script_dir/'log_harness_event.py'),'--repo-root',str(root),'--event-id',args.event_id,'--event-type','status_update','--severity','info','--category','manual_note','--status',args.status,'--surface','manual','--raw-excerpt',f'Status update for {args.event_id}','--linked-fix',args.linked_fix])
if __name__=='__main__': raise SystemExit(main())
