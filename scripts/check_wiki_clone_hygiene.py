#!/usr/bin/env python3
"""check_wiki_clone_hygiene.py — guard against duplicate / misconfigured wiki clones.

The Chromatic Wiki must have exactly ONE local clone, at the canonical path, on its
default branch. A second stale clone (e.g. the pre-rename ``Chromatic_Wiki`` folder
left behind after ``-Chromatic_Wiki`` -> ``chromatic-wiki``) is a split-brain hazard:
``promote_to_wiki.py`` could promote learnings into the wrong checkout, so the wiki
library silently diverges.

Checks (against CHROMATIC_WIKI_ROOT or the default canonical path):
  1. exactly ONE local clone of the wiki remote exists under the search root
  2. the canonical path exists and points at the expected remote
  3. (warn) the canonical clone sits on its default branch (a parked feature branch
     means the next promotion run branches from stale state)

A stale clone is retired by renaming it ``<name>.RETIRED-<date>`` (reversible: delete
once verified); dirs carrying the ``.RETIRED`` marker are skipped, so a sanctioned
retirement leaves this guard green.

Exit 0 = clean, 1 = violation. ``--json`` for machine output.

Usage:
  python scripts/check_wiki_clone_hygiene.py
  python scripts/check_wiki_clone_hygiene.py --json
  python scripts/check_wiki_clone_hygiene.py --clones-root <dir> --canonical <dir>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SYNC_CONFIG = _REPO / "config" / "wiki_harness_sync.yaml"
_DEFAULT_REMOTE = "kas1987/chromatic-wiki"
_DEFAULT_CANONICAL = Path(r"C:\Users\kas41\chromatic-wiki")


def _normalize_remote(url: str) -> str:
    """owner/repo identity from any git remote URL form (https / ssh / .git)."""
    u = url.strip().lower()
    if u.endswith(".git"):
        u = u[:-4]
    u = u.rstrip("/")
    # https://github.com/owner/repo  or  git@github.com:owner/repo
    u = u.replace("git@github.com:", "github.com/")
    parts = [p for p in u.replace(":", "/").split("/") if p]
    return "/".join(parts[-2:]) if len(parts) >= 2 else u


def _expected_remote() -> str:
    """Read wiki_repo from the sync config (DRY); fall back to the known default."""
    try:
        for line in _SYNC_CONFIG.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("wiki_repo:"):
                return _normalize_remote(stripped.split(":", 1)[1].strip())
    except OSError:
        pass
    return _DEFAULT_REMOTE


def _git(repo: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _is_clone_of(d: Path, expected: str) -> bool:
    if not (d / ".git").exists():
        return False
    url = _git(d, "remote", "get-url", "origin")
    return bool(url) and _normalize_remote(url) == expected


def _default_branch(repo: Path) -> str | None:
    ref = _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD")
    if ref:
        return ref.rsplit("/", 1)[-1]
    return None


def find_clones(clones_root: Path, expected: str) -> list[Path]:
    """Immediate subdirectories of clones_root that clone the expected wiki remote.

    Directories whose name carries the ``.RETIRED`` marker are skipped: tagging a
    stale clone ``<name>.RETIRED-<date>`` is the sanctioned, reversible way to retire
    it (rename now, delete once verified) without leaving this guard red.
    """
    if not clones_root.is_dir():
        return []
    found = []
    for child in sorted(clones_root.iterdir()):
        try:
            if not child.is_dir():
                continue
            if ".retired" in child.name.lower():
                continue
            if _is_clone_of(child, expected):
                found.append(child)
        except OSError:
            continue
    return found


def audit(clones_root: Path, canonical: Path, expected: str) -> dict:
    clones = find_clones(clones_root, expected)
    clone_strs = [str(p) for p in clones]
    failures: list[str] = []
    warnings: list[str] = []

    if len(clones) == 0:
        failures.append(f"no local clone of {expected} found under {clones_root} (expected canonical at {canonical})")
    elif len(clones) > 1:
        failures.append(
            f"{len(clones)} clones of {expected} found (expected exactly 1): "
            f"{clone_strs}. Retire the stale one(s); keep {canonical}."
        )

    canonical_is_clone = any(p.resolve() == canonical.resolve() for p in clones)
    if clones and not canonical_is_clone:
        failures.append(f"canonical path {canonical} is not the wiki clone; found instead {clone_strs}")

    if canonical_is_clone:
        branch = _git(canonical, "rev-parse", "--abbrev-ref", "HEAD")
        default = _default_branch(canonical) or "main"
        if branch and branch != default:
            warnings.append(
                f"canonical clone is on '{branch}', not its default '{default}' — "
                "the next promotion run will branch from a parked feature branch"
            )

    return {
        "ok": not failures,
        "expected_remote": expected,
        "clones_root": str(clones_root),
        "canonical": str(canonical),
        "clones": clone_strs,
        "failures": failures,
        "warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Guard against duplicate/misconfigured wiki clones")
    ap.add_argument("--canonical", type=Path, default=None, help="canonical wiki clone path")
    ap.add_argument("--clones-root", type=Path, default=None, help="dir to scan for clones")
    ap.add_argument("--remote", default=None, help="expected owner/repo (default: from sync config)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    expected = _normalize_remote(args.remote) if args.remote else _expected_remote()
    canonical = args.canonical or (
        Path(os.environ["CHROMATIC_WIKI_ROOT"]) if os.environ.get("CHROMATIC_WIKI_ROOT") else _DEFAULT_CANONICAL
    )
    clones_root = args.clones_root or canonical.parent

    report = audit(clones_root, canonical, expected)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "OK" if report["ok"] else "FAIL"
        print(f"[wiki-clone-hygiene] {status} — expected {expected}, {len(report['clones'])} clone(s)")
        for c in report["clones"]:
            print(f"  clone: {c}")
        for w in report["warnings"]:
            print(f"  WARN: {w}")
        for f in report["failures"]:
            print(f"  FAIL: {f}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
