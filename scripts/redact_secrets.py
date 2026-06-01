#!/usr/bin/env python3
"""redact_secrets.py — scrub secrets from text before it is logged.

PATTERNS are applied in order. Specific high-confidence token shapes come
first, then auth/cookie headers, then a generic ``key = value`` catch-all.
"""

from __future__ import annotations

import argparse
import re
import sys

PATTERNS = [
    # High-confidence provider token shapes.
    (re.compile(r"sk-proj-[A-Za-z0-9_\-]{12,}"), "sk-proj-[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "sk-[REDACTED]"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "ghp_[REDACTED]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "github_pat_[REDACTED]"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"), "xox-[REDACTED]"),  # Slack
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA[REDACTED]"),  # AWS access key id
    # Auth / cookie headers (CODE REVIEW: previously not redacted).
    (
        re.compile(r"(?i)(authorization\s*:\s*bearer)\s+\S+"),
        r"\1 [REDACTED]",
    ),
    (
        re.compile(r"(?i)((?:set-)?cookie\s*:)\s*\S+"),
        r"\1 [REDACTED]",
    ),
    # Generic key/value secrets. Capture an optional closing quote so the
    # whole quoted value is consumed (CODE REVIEW: missed closing quote).
    (
        re.compile(r"""(?i)(api[_-]?key|token|secret|password)(\s*[:=]\s*)["']?[^\s"']+["']?"""),
        r"\1\2[REDACTED]",
    ),
    # Private key blocks.
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.S,
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
]


def redact(text: str) -> tuple[str, bool]:
    changed = False
    for pat, repl in PATTERNS:
        new = pat.sub(repl, text)
        changed = changed or new != text
        text = new
    return text, changed


def main():
    ap = argparse.ArgumentParser(description="Redact secrets from text or stdin.")
    ap.add_argument("text", nargs="*")
    args = ap.parse_args()
    raw = " ".join(args.text) if args.text else sys.stdin.read()
    out, _ = redact(raw)
    print(out, end="" if out.endswith("\n") else "\n")


if __name__ == "__main__":
    main()
