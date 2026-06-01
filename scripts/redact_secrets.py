#!/usr/bin/env python3
from __future__ import annotations
import argparse
import re
import sys
PATTERNS=[
    (re.compile(r'sk-proj-[A-Za-z0-9_\-]{12,}'),'sk-proj-[REDACTED]'),
    (re.compile(r'sk-[A-Za-z0-9_\-]{20,}'),'sk-[REDACTED]'),
    (re.compile(r'ghp_[A-Za-z0-9]{20,}'),'ghp_[REDACTED]'),
    (re.compile(r'github_pat_[A-Za-z0-9_]{20,}'),'github_pat_[REDACTED]'),
    (re.compile(r'(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*["\']?[^\s"\']+'), r'\1=[REDACTED]'),
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----', re.S),'[REDACTED_PRIVATE_KEY]'),]
def redact(text: str) -> tuple[str,bool]:
    changed=False
    for pat,repl in PATTERNS:
        new=pat.sub(repl,text); changed=changed or new!=text; text=new
    return text,changed
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('text', nargs='*'); args=ap.parse_args(); raw=' '.join(args.text) if args.text else sys.stdin.read(); out,_=redact(raw); print(out, end='' if out.endswith('\n') else '\n')
if __name__=='__main__': main()
