#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path
from collections import Counter
from common_harness import repo_root,utc_now

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root'); ap.add_argument('--threshold', type=int, default=3); args=ap.parse_args(); root=Path(args.repo_root).resolve() if args.repo_root else repo_root(); log=root/'00_META/observability/ERROR_LOG.jsonl'; sigs=[]
    if log.exists():
        for line in log.read_text(encoding='utf-8').splitlines():
            if line.strip(): e=json.loads(line); sigs.append(e.get('error_signature') or e.get('category','unknown'))
    candidates=[(s,c) for s,c in Counter(sigs).items() if s and c>=args.threshold]
    if not candidates: print('No learning candidates above threshold.'); return
    path=root/'00_META/observability/LEARNINGS_LOG.md'
    with path.open('a', encoding='utf-8') as f:
        f.write(f'\n## Learning Candidates - {utc_now()}\n')
        for sig,c in candidates: f.write(f'\n- Pattern `{sig}` appeared {c} times. Review for playbook or fix-pattern update.\n')
    print(path)
if __name__=='__main__': main()
