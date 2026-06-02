#!/usr/bin/env python3
"""Run concurrent session maintenance and log the outcome."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from common_harness import run_safe  # noqa: E402


def _run(cmd: list[str], timeout: int = 180):
    return run_safe(cmd, cwd=REPO, timeout=timeout)


def _log_activity(summary: str, *, decision: str) -> None:
    lock_owner = os.environ.get("CHROMATIC_SESSION_ID", "").strip()
    cmd = [
        sys.executable,
        str(REPO / "scripts" / "log_agent_activity.py"),
        "log",
        "--event",
        "parallel.maintenance",
        "--lane",
        "agent",
        "--decision",
        decision,
        "--summary",
        summary[:500],
    ]
    if lock_owner:
        cmd.extend(["--lock-owner", lock_owner])
    _run(cmd, timeout=60)


def main() -> int:
    proc = _run([sys.executable, str(REPO / "scripts" / "parallel_health.py"), "--prune"])
    if proc.returncode != 0:
        summary = f"parallel maintenance failed (exit={proc.returncode})"
        _log_activity(summary, decision="failed")
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": summary,
                    "stdout": (proc.stdout or "")[-6000:],
                    "stderr": (proc.stderr or "")[-2000:],
                },
                indent=2,
            )
        )
        return proc.returncode or 1

    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        payload = {"ok": False, "error": "parallel_health output parse failed"}

    prune = payload.get("prune") or {}
    summary = (
        f"parallel maintenance complete: pruned_locks={prune.get('pruned_stale_locks', 0)}, "
        f"pruned_worktrees={prune.get('pruned_orphaned_worktrees', 0)}, "
        f"errors={len(prune.get('errors', []))}"
    )
    decision = "ok" if not prune.get("errors") else "review"
    _log_activity(summary, decision=decision)

    out = {
        "ok": True,
        "summary": summary,
        "parallel_health": payload,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
