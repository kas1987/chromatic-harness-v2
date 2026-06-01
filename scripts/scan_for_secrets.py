#!/usr/bin/env python3
"""scan_for_secrets.py — detect secret-shaped strings in repo files.

Modes:
    (default)   scan all eligible files under the repo root.
    --staged    scan only files staged for commit (fast pre-commit gate).

False positives: add an allowlist pragma comment on the offending line:
    api_key = "example"   # pragma: allowlist secret
Lines containing ``pragma: allowlist secret`` are ignored.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from common_harness import repo_root
from redact_secrets import PATTERNS

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
TEXT_EXT = {
    ".py",
    ".js",
    ".ts",
    ".json",
    ".md",
    ".yml",
    ".yaml",
    ".txt",
    ".toml",
    ".ini",
    ".sh",
    ".ps1",
}
ALLOWLIST_PRAGMA = "pragma: allowlist secret"
MAX_BYTES = 1_000_000


def is_text_target(p: Path) -> bool:
    if p.name.startswith(".env"):
        return True
    return p.suffix in TEXT_EXT


def iter_repo_files(root: Path):
    """Walk the tree pruning SKIP_DIRS in-place (avoids descending into them)."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if not is_text_target(p):
                continue
            try:
                if p.stat().st_size >= MAX_BYTES:
                    continue
            except OSError:
                continue
            yield p


def iter_staged_files(root: Path):
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return
    for rel in out.stdout.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        p = root / rel
        if p.is_file() and is_text_target(p) and not any(part in SKIP_DIRS for part in p.parts):
            yield p


def scan_file(p: Path) -> bool:
    """Return True if the file contains a non-allowlisted secret match."""
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    for line in text.splitlines():
        if ALLOWLIST_PRAGMA in line:
            continue
        for pat, _ in PATTERNS:
            if pat.search(line):
                return True
    return False


def main():
    ap = argparse.ArgumentParser(description="Detect secret-shaped strings in repo files.")
    ap.add_argument("--repo-root")
    ap.add_argument(
        "--staged",
        action="store_true",
        help="Scan only git-staged files (for pre-commit).",
    )
    args = ap.parse_args()
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()

    files = iter_staged_files(root) if args.staged else iter_repo_files(root)
    hits = []
    for p in files:
        if scan_file(p):
            hits.append(str(p.relative_to(root)))

    if hits:
        print("Potential secrets detected:", file=sys.stderr)
        for h in hits:
            print("- " + h, file=sys.stderr)
        print(
            "\nIf a match is a false positive, append '# pragma: allowlist secret' to the line.",
            file=sys.stderr,
        )
        return 1
    scope = "staged files" if args.staged else "repo"
    print(f"No obvious secrets detected ({scope}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
