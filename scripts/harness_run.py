#!/usr/bin/env python3
"""harness_run.py — terminal command wrapper with observability logging.

Runs an arbitrary command, streams its stdout/stderr, preserves the original
exit code, and on failure writes a redacted ``command_result`` event to
``00_META/observability/ERROR_LOG.jsonl``. Optionally routes the event.

Usage examples (see docs/observability/HARNESS_RUN.md for the full matrix):
    python scripts/harness_run.py -- npm run build
    python scripts/harness_run.py -- python scripts/foo.py --flag
    python scripts/harness_run.py --route -- pytest -q tests/test_foo.py
    python scripts/harness_run.py -- bash -c "make lint && make test"
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

from common_harness import (
    append_jsonl,
    event_id,
    git_state,
    repo_root,
    utc_now,
    validate_record,
)
from redact_secrets import redact

# Conventional shell exit code for "command not found / not executable".
EXIT_COMMAND_NOT_FOUND = 127


def _log_failure(root, args, cmd, returncode, output, signature):
    """Build, validate, append (and optionally route) a failure event.

    Returns the event_id on success, or None if the event was invalid.
    """
    excerpt, changed = redact((output or "")[-4000:])
    ev = {
        "event_id": event_id(),
        "timestamp": utc_now(),
        "repo": root.name,
        "workspace": str(root),
        "source": {
            "surface": args.surface,
            "agent": args.agent,
            "model": args.model,
            "session_id": args.session_id,
        },
        "event_type": "command_result",
        "severity": args.severity_on_fail,
        "category": args.category_on_fail,
        "status": "open",
        "command": " ".join(shlex.quote(x) for x in cmd),
        "exit_code": returncode,
        "files_touched": [],
        "error_signature": signature,
        "raw_excerpt": excerpt,
        "redacted": changed,
        "suspected_cause": "",
        "action_taken": "command failure logged by harness_run.py",
        "linked_fix": None,
        "linked_learning": None,
        "next_action": "route event for remediation",
        "metadata": {"git": git_state(root)},
    }
    errs = validate_record(ev)
    if errs:
        print("Unable to log invalid event: " + str(errs), file=sys.stderr)
        return None
    append_jsonl(root / "00_META/observability/ERROR_LOG.jsonl", ev)
    print(f"\nHarness event logged: {ev['event_id']}", file=sys.stderr)
    if args.route:
        # route_event.py lives alongside this wrapper, not under the target
        # --repo-root (which may be any data tree without a scripts/ dir).
        router = Path(__file__).resolve().parent / "route_event.py"
        subprocess.run(
            [
                sys.executable,
                str(router),
                "--repo-root",
                str(root),
                "--event-id",
                ev["event_id"],
            ],
            check=False,
        )
    return ev["event_id"]


def main():
    ap = argparse.ArgumentParser(description="Run a command and log failed results to Harness observability.")
    ap.add_argument("--repo-root")
    ap.add_argument("--surface", default="terminal")
    ap.add_argument("--agent", default="")
    ap.add_argument("--model", default="")
    ap.add_argument("--session-id", default="")
    ap.add_argument("--severity-on-fail", default="medium")
    ap.add_argument("--category-on-fail", default="command_failure")
    ap.add_argument("--route", action="store_true")
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    # Strip a leading "--" separator if present, then require a real command.
    raw = args.command
    cmd = raw[1:] if raw and raw[0] == "--" else raw
    if not cmd:
        print(
            "No command provided. Usage: python scripts/harness_run.py -- npm run build",
            file=sys.stderr,
        )
        return 2

    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()

    try:
        proc = subprocess.run(cmd, cwd=str(root), text=True, capture_output=True)
    except FileNotFoundError as exc:
        # Command binary does not exist — still an observable failure.
        msg = f"command not found: {cmd[0]} ({exc})"
        print(msg, file=sys.stderr)
        _log_failure(
            root,
            args,
            cmd,
            EXIT_COMMAND_NOT_FOUND,
            msg,
            "command_not_found",
        )
        return EXIT_COMMAND_NOT_FOUND

    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)

    if proc.returncode != 0:
        _log_failure(
            root,
            args,
            cmd,
            proc.returncode,
            proc.stderr or proc.stdout or "",
            f"command_failed_exit_{proc.returncode}",
        )

    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
