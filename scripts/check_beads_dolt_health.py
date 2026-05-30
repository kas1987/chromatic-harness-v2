#!/usr/bin/env python3
"""Beads Dolt sync health check — actionable exit codes for session closeout."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from intake.bd_runner import resolve_bd_argv  # noqa: E402

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    if cmd and cmd[0] == "bd":
        cmd = resolve_bd_argv() + cmd[1:]
        if cmd[0] == "bd":
            return subprocess.CompletedProcess(cmd, returncode=127, stdout="", stderr="bd not on PATH")
    return subprocess.run(
        cmd,
        cwd=cwd or REPO,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def _git_dir_cache() -> Path | None:
    base = REPO / ".beads" / "embeddeddolt" / "chromatic_harness_v2" / ".dolt" / "git-remote-cache"
    if not base.is_dir():
        return None
    for child in base.iterdir():
        repo = child / "repo.git"
        if repo.is_dir():
            return repo
    return None


def _repair_cache_head(git_dir: Path) -> bool:
    """Bootstrap bare cache repo when HEAD has no commits (fixes ambiguous HEAD)."""
    proc = _run(["git", "--git-dir", str(git_dir), "rev-parse", "HEAD"], timeout=10)
    if proc.returncode == 0 and proc.stdout.strip() and proc.stdout.strip() != "HEAD":
        return True
    commit = _run(
        ["git", "--git-dir", str(git_dir), "commit-tree", EMPTY_TREE, "-m", "dolt remote cache bootstrap"],
        timeout=10,
    )
    if commit.returncode != 0 or not commit.stdout.strip():
        return False
    ref = _run(
        ["git", "--git-dir", str(git_dir), "update-ref", "refs/heads/master", commit.stdout.strip()],
        timeout=10,
    )
    return ref.returncode == 0


def check(*, try_push: bool = False, push_timeout: int = 180) -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True

    embedded = REPO / ".beads" / "embeddeddolt"
    if not embedded.is_dir():
        messages.append("WARN: .beads/embeddeddolt missing — run `bd init` in repo root")
        ok = False

    proc = _run(["git", "rev-parse", "HEAD"], cwd=REPO)
    if proc.returncode != 0:
        messages.append("FAIL: main git repo has no HEAD — checkout a branch before `bd dolt push`")
        ok = False

    cache = _git_dir_cache()
    if cache:
        if not _repair_cache_head(cache):
            messages.append(
                "FAIL: Dolt git-remote-cache has invalid HEAD — see docs/beads/DOLT_SYNC_TROUBLESHOOTING.md"
            )
            ok = False
        else:
            messages.append("OK: Dolt git-remote-cache HEAD valid")
    else:
        messages.append("WARN: no git-remote-cache yet (first push may create it)")

    remote_list = _run(["bd", "dolt", "remote", "list"], timeout=30)
    if remote_list.returncode == 127:
        messages.append("WARN: bd not on PATH — skip remote list")
    elif remote_list.returncode != 0:
        messages.append(f"FAIL: bd dolt remote list: {(remote_list.stderr or remote_list.stdout).strip()}")
        ok = False
    elif "origin" not in (remote_list.stdout or ""):
        messages.append(
            "WARN: no Dolt remote 'origin' — run: bd dolt remote add origin <git-url>"
        )

    if try_push:
        push = _run(["bd", "dolt", "push"], timeout=push_timeout)
        if push.returncode == 0:
            messages.append("OK: bd dolt push succeeded")
        else:
            ok = False
            err = (push.stderr or push.stdout or "").strip()
            messages.append(f"FAIL: bd dolt push: {err[:800]}")
            if "ambiguous argument 'HEAD'" in err:
                messages.append("HINT: repair cache HEAD (this script does automatically on next run)")
            if "direct push to main/master is blocked" in err:
                messages.append(
                    "HINT: ensure pre-push allows refs/dolt/* — see .beads/hooks/pre-push.sh"
                )
            if "credential" in err.lower() or "authentication" in err.lower():
                messages.append(
                    "HINT: configure non-interactive HTTPS (GCM) or SSH for GitHub"
                )

    return ok, messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Check beads Dolt sync health")
    parser.add_argument("--try-push", action="store_true", help="Run bd dolt push (slow)")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any failure")
    args = parser.parse_args()

    ok, messages = check(try_push=args.try_push)
    for line in messages:
        print(line)
    if args.strict and not ok:
        return 1
    if not ok and args.try_push:
        return 1
    return 0 if ok else (0 if not args.strict else 1)


if __name__ == "__main__":
    raise SystemExit(main())
