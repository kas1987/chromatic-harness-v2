#!/usr/bin/env python3
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from redact_secrets import PATTERNS
from common_harness import repo_root
SKIP_DIRS={'.git','node_modules','.venv','venv','__pycache__','dist','build'}
TEXT_EXT={'.py','.js','.ts','.json','.md','.yml','.yaml','.txt','.toml','.ini','.sh','.ps1'}
def should_scan(p):
    if any(part in SKIP_DIRS for part in p.parts): return False
    if p.name.startswith('.env'): return True
    return p.suffix in TEXT_EXT and p.stat().st_size < 1_000_000
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root'); args=ap.parse_args(); root=Path(args.repo_root).resolve() if args.repo_root else repo_root(); hits=[]
    for p in root.rglob('*'):
        if not p.is_file() or not should_scan(p): continue
        try: text=p.read_text(encoding='utf-8', errors='ignore')
        except Exception: continue
        for pat,_ in PATTERNS:
            if pat.search(text): hits.append(str(p.relative_to(root))); break
    if hits:
        print('Potential secrets detected:', file=sys.stderr)
        for h in hits: print('- '+h, file=sys.stderr)
        return 1
    print('No obvious secrets detected.'); return 0
if __name__=='__main__': raise SystemExit(main())
