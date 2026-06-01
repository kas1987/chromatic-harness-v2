#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path
from common_harness import repo_root

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--event-id', required=True); ap.add_argument('--repo-root'); args=ap.parse_args(); root=Path(args.repo_root).resolve() if args.repo_root else repo_root()
    for line in (root/'00_META/observability/ERROR_LOG.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            rec=json.loads(line)
            if rec.get('event_id')==args.event_id: print(json.dumps(rec, indent=2)); return
    raise SystemExit(f'event not found: {args.event_id}')
if __name__=='__main__': main()
