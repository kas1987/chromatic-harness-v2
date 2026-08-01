#!/usr/bin/env python3
"""AUTO_CLEAN — Chromatic Harness V2 comprehensive cleanup script.

Idempotent and safe to run on any schedule. All destructive operations are
gated behind --force; default mode is --dry-run (read-only reporting).

Checks performed:
  1. Remove *.pyc files and __pycache__ directories
  2. Prune stale git worktrees (git worktree prune)
  3. Remove empty directories (except those containing .gitkeep)
  4. Report files > 5 MB that may be accidental large-file commits
  5. Report stale log files older than 30 days in 07_LOGS_AND_AUDIT/
  6. Remove *.log files older than 7 days from 07_LOGS_AND_AUDIT/
  7. Check for .pyc files tracked by git
  8. Print a clean summary

Exit codes:
  0 — success (no errors; warnings or dry-run actions are not errors)
  1 — one or more checks raised an unrecoverable error
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HARNESS_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = HARNESS_ROOT / "07_LOGS_AND_AUDIT"

# ---------------------------------------------------------------------------
# ANSI colours (no external deps)
# ---------------------------------------------------------------------------
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_RED    = "\033[31m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_GREY   = "\033[90m"

def _c(text: str, *codes: str) -> str:
    return "".join(codes) + str(text) + _RESET

def info(msg: str) -> None:
    print(_c("  " + msg, _CYAN))

def ok(msg: str) -> None:
    print(_c("  ✓ " + msg, _GREEN))

def warn(msg: str) -> None:
    print(_c("  ⚠ " + msg, _YELLOW))

def err(msg: str) -> None:
    print(_c("  ✗ " + msg, _RED), file=sys.stderr)

def header(msg: str) -> None:
    print()
    print(_c(f"{'─' * 60}", _BOLD))
    print(_c(f"  {msg}", _BOLD))
    print(_c(f"{'─' * 60}", _BOLD))

def dim(msg: str) -> None:
    print(_c("    " + msg, _GREY))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a subprocess, return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or HARNESS_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return 1, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 1, "", f"command timed out: {' '.join(cmd)}"


def _age_days(path: Path) -> float:
    """Return file age in days based on mtime."""
    return (time.time() - path.stat().st_mtime) / 86_400


def _size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


# ---------------------------------------------------------------------------
# Check 1 — *.pyc files and __pycache__ directories
# ---------------------------------------------------------------------------

def clean_pycache(dry_run: bool) -> dict:
    header("1 · Python cache files (*.pyc / __pycache__)")
    pyc_files: list[Path] = []
    cache_dirs: list[Path] = []

    for p in HARNESS_ROOT.rglob("*.pyc"):
        pyc_files.append(p)

    for p in HARNESS_ROOT.rglob("__pycache__"):
        if p.is_dir():
            cache_dirs.append(p)

    removed_files = 0
    removed_dirs = 0

    for f in pyc_files:
        dim(f"pyc: {f.relative_to(HARNESS_ROOT)}")
        if not dry_run:
            try:
                f.unlink(missing_ok=True)
                removed_files += 1
            except OSError as exc:
                warn(f"could not remove {f}: {exc}")
        else:
            removed_files += 1

    for d in cache_dirs:
        dim(f"dir: {d.relative_to(HARNESS_ROOT)}")
        if not dry_run:
            try:
                # Only remove if empty (pycs already deleted above)
                for child in d.rglob("*"):
                    if child.is_file():
                        child.unlink(missing_ok=True)
                d.rmdir()
                removed_dirs += 1
            except OSError as exc:
                warn(f"could not remove {d}: {exc}")
        else:
            removed_dirs += 1

    label = "would remove" if dry_run else "removed"
    if removed_files or removed_dirs:
        ok(f"{label} {removed_files} *.pyc file(s) and {removed_dirs} __pycache__ dir(s)")
    else:
        ok("no Python cache artefacts found")

    return {"pyc_files": removed_files, "cache_dirs": removed_dirs}


# ---------------------------------------------------------------------------
# Check 2 — git worktree prune
# ---------------------------------------------------------------------------

def prune_worktrees(dry_run: bool) -> dict:
    header("2 · Git worktree prune")
    cmd = ["git", "worktree", "prune"] + (["--dry-run"] if dry_run else [])
    rc, stdout, stderr = _run(cmd)

    if rc != 0:
        warn(f"git worktree prune returned {rc}: {stderr}")
        return {"status": "error"}

    if stdout:
        for line in stdout.splitlines():
            dim(line)
        ok(f"worktrees pruned{' (dry-run)' if dry_run else ''}")
    else:
        ok("no stale worktrees found")

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Check 3 — Remove empty directories
# ---------------------------------------------------------------------------

def remove_empty_dirs(dry_run: bool) -> dict:
    header("3 · Empty directories")
    removed = 0
    candidates: list[Path] = []

    # Walk bottom-up so nested empties are caught in one pass
    for p in sorted(HARNESS_ROOT.rglob("*"), reverse=True):
        if not p.is_dir():
            continue
        # Skip .git internals
        if ".git" in p.parts:
            continue
        children = list(p.iterdir())
        if not children:
            candidates.append(p)
        elif all(c.name == ".gitkeep" for c in children):
            # Has only .gitkeep — intentionally kept, skip
            pass

    for d in candidates:
        dim(f"empty: {d.relative_to(HARNESS_ROOT)}")
        if not dry_run:
            try:
                d.rmdir()
                removed += 1
            except OSError as exc:
                warn(f"could not remove {d}: {exc}")
        else:
            removed += 1

    label = "would remove" if dry_run else "removed"
    if removed:
        ok(f"{label} {removed} empty director{'ies' if removed != 1 else 'y'}")
    else:
        ok("no empty directories found")

    return {"empty_dirs_removed": removed}


# ---------------------------------------------------------------------------
# Check 4 — Large files (> 5 MB)
# ---------------------------------------------------------------------------

LARGE_FILE_THRESHOLD_MB = 5.0
# Patterns to skip when scanning for large files
_LARGE_FILE_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__"}


def check_large_files() -> dict:
    header("4 · Large files (> 5 MB)")
    found: list[tuple[Path, float]] = []

    for p in HARNESS_ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in _LARGE_FILE_SKIP_DIRS for part in p.parts):
            continue
        try:
            mb = _size_mb(p)
        except OSError:
            continue
        if mb > LARGE_FILE_THRESHOLD_MB:
            found.append((p, mb))

    found.sort(key=lambda x: x[1], reverse=True)

    if found:
        warn(f"{len(found)} file(s) exceed {LARGE_FILE_THRESHOLD_MB} MB — review before committing:")
        for path, mb in found:
            dim(f"  {mb:7.1f} MB  {path.relative_to(HARNESS_ROOT)}")
    else:
        ok(f"no files exceed {LARGE_FILE_THRESHOLD_MB} MB")

    return {"large_files": len(found), "items": [(str(p.relative_to(HARNESS_ROOT)), round(mb, 2)) for p, mb in found]}


# ---------------------------------------------------------------------------
# Check 5 — Stale logs older than 30 days (report only)
# ---------------------------------------------------------------------------

STALE_LOG_DAYS = 30


def report_stale_logs() -> dict:
    header(f"5 · Stale logs (> {STALE_LOG_DAYS} days) in 07_LOGS_AND_AUDIT/")

    if not LOGS_DIR.exists():
        warn(f"07_LOGS_AND_AUDIT/ not found at {LOGS_DIR}")
        return {"stale_logs": 0}

    stale: list[tuple[Path, float]] = []
    for p in LOGS_DIR.rglob("*"):
        if not p.is_file():
            continue
        try:
            age = _age_days(p)
        except OSError:
            continue
        if age > STALE_LOG_DAYS:
            stale.append((p, age))

    stale.sort(key=lambda x: x[1], reverse=True)

    if stale:
        warn(f"{len(stale)} log file(s) older than {STALE_LOG_DAYS} days:")
        for path, age in stale[:20]:  # cap display at 20
            dim(f"  {age:6.0f} d  {path.relative_to(HARNESS_ROOT)}")
        if len(stale) > 20:
            dim(f"  ... and {len(stale) - 20} more")
    else:
        ok(f"no log files older than {STALE_LOG_DAYS} days")

    return {"stale_logs": len(stale)}


# ---------------------------------------------------------------------------
# Check 6 — Remove *.log files older than 7 days
# ---------------------------------------------------------------------------

OLD_LOG_DAYS = 7


def clean_old_logs(dry_run: bool) -> dict:
    header(f"6 · Remove *.log files older than {OLD_LOG_DAYS} days from 07_LOGS_AND_AUDIT/")

    if not LOGS_DIR.exists():
        warn(f"07_LOGS_AND_AUDIT/ not found at {LOGS_DIR}")
        return {"removed": 0}

    candidates: list[tuple[Path, float]] = []
    for p in LOGS_DIR.rglob("*.log"):
        if not p.is_file():
            continue
        try:
            age = _age_days(p)
        except OSError:
            continue
        if age > OLD_LOG_DAYS:
            candidates.append((p, age))

    candidates.sort(key=lambda x: x[1], reverse=True)
    removed = 0

    for path, age in candidates:
        dim(f"  {age:6.0f} d  {path.relative_to(HARNESS_ROOT)}")
        if not dry_run:
            try:
                path.unlink(missing_ok=True)
                removed += 1
            except OSError as exc:
                warn(f"could not remove {path}: {exc}")
        else:
            removed += 1

    label = "would remove" if dry_run else "removed"
    if removed:
        ok(f"{label} {removed} *.log file(s) older than {OLD_LOG_DAYS} days")
    else:
        ok(f"no *.log files older than {OLD_LOG_DAYS} days found")

    return {"removed": removed}


# ---------------------------------------------------------------------------
# Check 7 — .pyc files tracked by git
# ---------------------------------------------------------------------------

def check_git_tracked_pyc() -> dict:
    header("7 · Git-tracked *.pyc files")
    rc, stdout, stderr = _run(["git", "ls-files", "--cached", "*.pyc"])

    tracked: list[str] = []
    if rc == 0 and stdout:
        tracked = [line.strip() for line in stdout.splitlines() if line.strip()]

    if tracked:
        err(f"{len(tracked)} *.pyc file(s) are tracked by git — add to .gitignore and remove:")
        for entry in tracked:
            dim(f"  {entry}")
    else:
        ok("no *.pyc files are tracked by git")

    return {"tracked_pyc": len(tracked), "files": tracked}


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(results: dict, dry_run: bool, errors: bool) -> None:
    header("Summary")

    mode_tag = _c(" DRY-RUN (pass --force to apply changes) ", _YELLOW, _BOLD) if dry_run else _c(" APPLIED ", _GREEN, _BOLD)
    print(f"  Mode: {mode_tag}")
    print()

    rows = [
        ("Python cache files removed/would-remove",
         results.get("pyc", {}).get("pyc_files", 0)),
        ("__pycache__ dirs removed/would-remove",
         results.get("pyc", {}).get("cache_dirs", 0)),
        ("Worktree prune",
         results.get("worktrees", {}).get("status", "ok")),
        ("Empty dirs removed/would-remove",
         results.get("empty_dirs", {}).get("empty_dirs_removed", 0)),
        ("Large files (> 5 MB)",
         results.get("large_files", {}).get("large_files", 0)),
        ("Stale logs (> 30 d, report only)",
         results.get("stale_logs", {}).get("stale_logs", 0)),
        ("*.log files removed/would-remove (> 7 d)",
         results.get("old_logs", {}).get("removed", 0)),
        ("Git-tracked *.pyc files",
         results.get("tracked_pyc", {}).get("tracked_pyc", 0)),
    ]

    for label, value in rows:
        colour = _RED if isinstance(value, int) and value > 0 else _GREEN
        value_str = _c(str(value), colour)
        print(f"  {label:<45} {value_str}")

    print()
    if errors:
        err("One or more checks encountered errors — review output above.")
    else:
        ok(_c("All checks complete.", _BOLD))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AUTO_CLEAN — Chromatic Harness V2 cleanup script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="Preview actions without modifying anything (default)",
    )
    mode.add_argument(
        "--force",
        dest="dry_run",
        action="store_false",
        help="Actually perform deletions",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dry_run: bool = args.dry_run

    print(_c(f"\n{'═' * 60}", _BOLD))
    print(_c("  AUTO_CLEAN — Chromatic Harness V2", _BOLD, _CYAN))
    print(_c(f"  Root: {HARNESS_ROOT}", _GREY))
    mode_display = _c("DRY-RUN (read-only)", _YELLOW) if dry_run else _c("FORCE (destructive)", _RED, _BOLD)
    print(_c(f"  Mode: ", _BOLD) + mode_display)
    print(_c(f"{'═' * 60}", _BOLD))

    errors = False
    results: dict = {}

    try:
        results["pyc"] = clean_pycache(dry_run)
    except Exception as exc:
        err(f"check 1 failed: {exc}")
        errors = True

    try:
        results["worktrees"] = prune_worktrees(dry_run)
        if results["worktrees"].get("status") == "error":
            errors = True
    except Exception as exc:
        err(f"check 2 failed: {exc}")
        errors = True

    try:
        results["empty_dirs"] = remove_empty_dirs(dry_run)
    except Exception as exc:
        err(f"check 3 failed: {exc}")
        errors = True

    try:
        results["large_files"] = check_large_files()
    except Exception as exc:
        err(f"check 4 failed: {exc}")
        errors = True

    try:
        results["stale_logs"] = report_stale_logs()
    except Exception as exc:
        err(f"check 5 failed: {exc}")
        errors = True

    try:
        results["old_logs"] = clean_old_logs(dry_run)
    except Exception as exc:
        err(f"check 6 failed: {exc}")
        errors = True

    try:
        results["tracked_pyc"] = check_git_tracked_pyc()
        if results["tracked_pyc"].get("tracked_pyc", 0) > 0:
            errors = True
    except Exception as exc:
        err(f"check 7 failed: {exc}")
        errors = True

    print_summary(results, dry_run, errors)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
