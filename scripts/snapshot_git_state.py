#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
from common_harness import git_state,repo_root,utc_now,write_json

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root'); ap.add_argument('--out', default='.chromatic/last_known_good.json'); args=ap.parse_args(); root=Path(args.repo_root).resolve() if args.repo_root else repo_root(); out=Path(args.out); out=out if out.is_absolute() else root/out; write_json(out, {'captured_at':utc_now(),'repo':root.name,'git':git_state(root)}); print(out)
if __name__=='__main__': main()
