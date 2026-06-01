#!/usr/bin/env python3
"""Redact likely secrets from text before writing Harness logs."""

from __future__ import annotations

import re
import sys

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^\s'\"]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
]


def redact_text(text: str) -> tuple[str, bool]:
    redacted = False
    output = text or ""
    for pattern in SECRET_PATTERNS:
        output, count = pattern.subn("[REDACTED_SECRET]", output)
        if count:
            redacted = True
    return output, redacted


if __name__ == "__main__":
    incoming = sys.stdin.read()
    cleaned, _ = redact_text(incoming)
    print(cleaned, end="")
