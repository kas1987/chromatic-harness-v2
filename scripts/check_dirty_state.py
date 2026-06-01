#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
from common_harness import git_state,repo_root

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root'); args=ap.parse_args(); root=Path(args.repo_root).resolve() if args.repo_root else repo_root(); st=git_state(root)
    if st['dirty']:
        print('Dirty working tree:'); print('\n'.join(st['status_porcelain'])); return 1
    print('Working tree clean.'); return 0
if __name__=='__main__': raise SystemExit(main())
