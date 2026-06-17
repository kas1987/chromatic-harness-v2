#!/usr/bin/env python3
"""Large-file & stale-tracked-file gate.

Prevents two recurring repo-hygiene regressions:

  1. **Oversized blobs** — a file larger than ``--block-mb`` (default 45 MB,
     just under GitHub's 50 MB hard warning) is committed, bloating history
     and tripping LFS warnings on push.
  2. **Re-adding ignored files** — a file that matches ``.gitignore`` gets
     force-added back into the index (how ``WORKFLOW_RUN_LOG.jsonl`` ended up
     a 59 MB tracked log despite being ignored).

Default scope is the **staged** changeset (``--staged``), so the pre-commit
hook only judges what is about to be committed. ``--all`` audits every tracked
file (use in CI to catch drift). Genuine large assets that must live in git
(e.g. via Git LFS) can be allow-listed in ``.large-file-allowlist`` (one glob
per line, ``#`` comments allowed).

Exit code is non-zero if any BLOCK-level finding exists, so it can gate a
commit / CI job. WARN-level findings print but do not fail.

Usage:
    python scripts/large_file_gate.py --staged          # pre-commit
    python scripts/large_file_gate.py --all             # CI audit
    python scripts/large_file_gate.py path/to/file ...  # explicit
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

DEFAULT_WARN_MB = 5.0
DEFAULT_BLOCK_MB = 45.0
ALLOWLIST_FILE = ".large-file-allowlist"
_MB = 1024 * 1024


def _repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(out.stdout.strip())
    except Exception:
        return Path.cwd()


def load_allowlist(repo_root: Path) -> list[str]:
    """Return glob patterns for files exempt from the size block."""
    f = repo_root / ALLOWLIST_FILE
    if not f.is_file():
        return []
    pats = []
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pats.append(line)
    return pats


def is_allowlisted(rel_path: str, patterns) -> bool:
    return any(fnmatch.fnmatch(rel_path, pat) for pat in patterns)


def classify(size_bytes: int, warn_mb: float, block_mb: float) -> str | None:
    """Return 'BLOCK', 'WARN', or None for a given size."""
    if size_bytes >= block_mb * _MB:
        return "BLOCK"
    if size_bytes >= warn_mb * _MB:
        return "WARN"
    return None


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [p for p in out.stdout.splitlines() if p.strip()]


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [p for p in out.stdout.splitlines() if p.strip()]


def ignored_matches(paths) -> set[str]:
    """Subset of *paths* that match a .gitignore rule (regardless of tracking)."""
    if not paths:
        return set()
    proc = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        input="\n".join(paths),
        capture_output=True,
        text=True,
        check=False,
    )
    return {p for p in proc.stdout.splitlines() if p.strip()}


def scan(paths, repo_root: Path, warn_mb: float, block_mb: float):
    """Return list of (level, rel_path, detail). Pure given the filesystem."""
    allow = load_allowlist(repo_root)
    findings = []
    ignored = ignored_matches(list(paths))
    for rel in paths:
        abs = repo_root / rel
        if not abs.is_file():  # skip submodules (gitlinks) / deletions / dirs
            continue
        size = abs.stat().st_size
        if rel in ignored:
            findings.append(("BLOCK", rel, "tracked/staged but matches .gitignore"))
            continue
        if is_allowlisted(rel, allow):
            continue
        level = classify(size, warn_mb, block_mb)
        if level:
            findings.append((level, rel, f"{size / _MB:.1f} MB"))
    return findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Block oversized / re-added-ignored files.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true", help="scan staged changes (default)")
    g.add_argument("--all", action="store_true", help="scan all tracked files")
    ap.add_argument("paths", nargs="*", help="explicit paths to scan")
    ap.add_argument("--warn-mb", type=float, default=DEFAULT_WARN_MB)
    ap.add_argument("--block-mb", type=float, default=DEFAULT_BLOCK_MB)
    args = ap.parse_args(argv)

    repo = _repo_root()
    if args.paths:
        # paths may be absolute or repo-relative; normalise to repo-relative
        rels = []
        for p in args.paths:
            pp = Path(p)
            try:
                rels.append(
                    str((pp if pp.is_absolute() else (repo / pp)).resolve().relative_to(repo)).replace("\\", "/")
                )
            except ValueError:
                rels.append(p)
        paths = rels
    elif args.all:
        paths = tracked_files()
    else:  # default: staged
        paths = staged_files()

    findings = scan(paths, repo, args.warn_mb, args.block_mb)
    blocks = [f for f in findings if f[0] == "BLOCK"]
    warns = [f for f in findings if f[0] == "WARN"]

    for level, rel, detail in findings:
        print(f"[large-file-gate] {level}: {rel} ({detail})", file=sys.stderr)

    if blocks:
        print(
            f"\n[large-file-gate] {len(blocks)} blocking finding(s). "
            "Untrack the file (git rm --cached + .gitignore), use Git LFS, or "
            f"add a glob to {ALLOWLIST_FILE} if it is a genuine, intended asset.",
            file=sys.stderr,
        )
        return 1
    if warns:
        print(f"[large-file-gate] {len(warns)} warning(s); not blocking.", file=sys.stderr)
    else:
        print("[large-file-gate] OK — no oversized or re-added-ignored files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
