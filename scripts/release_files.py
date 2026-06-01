#!/usr/bin/env python3
from __future__ import annotations
import argparse
import os
from pathlib import Path
from common_harness import read_json,write_json,repo_root,utc_now

def main():
    ap=argparse.ArgumentParser(description='Release active writer claims'); ap.add_argument('--repo-root'); ap.add_argument('--session', default=os.environ.get('CHROMATIC_SESSION_ID','manual')); ap.add_argument('--files', nargs='*'); ap.add_argument('--all-for-session', action='store_true'); args=ap.parse_args()
    root=Path(args.repo_root).resolve() if args.repo_root else repo_root(); path=root/'.chromatic/active_writers.json'; data=read_json(path, {'claims':{}}); claims=data.setdefault('claims',{}); targets=set(args.files or []); removed=[]
    for f,cur in list(claims.items()):
        if args.all_for_session and cur.get('session')==args.session: removed.append(f); del claims[f]
        elif targets and f in targets and cur.get('session')==args.session: removed.append(f); del claims[f]
    data['updated_at']=utc_now(); write_json(path,data); print(f'released {len(removed)} claim(s)')
if __name__=='__main__': main()
