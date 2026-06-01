#!/usr/bin/env python3
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path
from common_harness import read_json,write_json,repo_root,utc_now

def norm(root,f):
    p=Path(f); return str(p.resolve()) if p.is_absolute() else str((root/p).resolve().relative_to(root))
def main():
    ap=argparse.ArgumentParser(description='Claim files before agent/IDE mutation'); ap.add_argument('--repo-root'); ap.add_argument('--writer', required=True); ap.add_argument('--session', default=os.environ.get('CHROMATIC_SESSION_ID','manual')); ap.add_argument('--task', default='unknown'); ap.add_argument('--files', nargs='+', required=True); ap.add_argument('--force', action='store_true'); args=ap.parse_args()
    root=Path(args.repo_root).resolve() if args.repo_root else repo_root(); path=root/'.chromatic/active_writers.json'; data=read_json(path, {'claims':{}}); claims=data.setdefault('claims',{}); blocked=[]
    for f in args.files:
        nf=norm(root,f); cur=claims.get(nf)
        if cur and cur.get('session')!=args.session and not args.force: blocked.append((nf,cur))
    if blocked:
        print('CLAIM BLOCKED: existing active writer(s)', file=sys.stderr)
        for f,cur in blocked: print(f'- {f}: {cur}', file=sys.stderr)
        return 3
    for f in args.files: claims[norm(root,f)]={'writer':args.writer,'session':args.session,'task':args.task,'claimed_at':utc_now()}
    data['updated_at']=utc_now(); write_json(path,data); print(f'claimed {len(args.files)} file(s) for session {args.session}'); return 0
if __name__=='__main__': raise SystemExit(main())
