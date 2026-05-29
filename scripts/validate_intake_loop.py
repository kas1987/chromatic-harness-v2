#!/usr/bin/env python3
"""Validate P0 intake close-loop: queue → auto_intake → workflow_go.

Exit 0 when the pipeline contract holds (dry-run / subprocess checks).
Does not create real beads unless --live is passed.

Usage:
  python scripts/validate_intake_loop.py
  python scripts/validate_intake_loop.py --verbose
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from intake.auto_intake import drain_queue, simple_decompose  # noqa: E402
from intake.queue import append_entry, list_queued, validate_entry  # noqa: E402

PYTHON = sys.executable


def _log(msg: str, *, verbose: bool) -> None:
    if verbose:
        print(msg)


def check_schema_and_decompose(verbose: bool) -> list[str]:
    errors: list[str] = []
    sample = {
        "id": "validate-loop-goal",
        "source": "manual",
        "kind": "goal",
        "status": "queued",
        "title": "Validate intake loop",
        "goal": "- Step one\n- Step two",
        "queued_at": "2026-05-29T12:00:00Z",
    }
    errs = validate_entry(sample)
    if errs:
        errors.append(f"schema validation failed: {errs}")
    tasks = simple_decompose(sample["goal"])
    if len(tasks) < 2:
        errors.append("simple_decompose expected 2 bullet tasks")
    _log(f"decompose ok: {len(tasks)} tasks", verbose=verbose)
    return errors


def check_drain_dry_run(queue: Path, verbose: bool) -> list[str]:
    errors: list[str] = []
    append_entry(
        {
            "id": "validate-dispatch-1",
            "source": "bead_hook",
            "kind": "bead_dispatch",
            "status": "queued",
            "title": "Dry dispatch",
            "bead_id": "chromatic-harness-v2-validate",
        },
        path=queue,
    )
    append_entry(
        {
            "id": "validate-goal-1",
            "source": "manual",
            "kind": "goal",
            "status": "queued",
            "title": "Loop goal",
            "goal": "Single validation goal",
            "priority": "P2",
        },
        path=queue,
    )
    queued_before = len(list_queued(path=queue))
    report = drain_queue(repo_root=REPO, queue_path=queue, dry_run=True)
    _log(f"drain dry-run: {report.to_dict()}", verbose=verbose)
    if report.processed < 2:
        errors.append(f"expected 2 processed dry-run, got {report.processed}")
    if queued_before < 2:
        errors.append("queued entries not visible before drain")
    return errors


def check_workflow_go_audit(verbose: bool) -> list[str]:
    errors: list[str] = []
    proc = subprocess.run(
        [PYTHON, str(REPO / "scripts" / "workflow_go.py"), "GO AUDIT"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if proc.returncode != 0:
        errors.append(f"workflow_go GO AUDIT failed: {proc.stderr[:300]}")
        return errors
    try:
        data = json.loads(proc.stdout.strip())
    except json.JSONDecodeError as exc:
        errors.append(f"GO AUDIT invalid JSON: {exc}")
        return errors
    if data.get("mode") != "GO AUDIT":
        errors.append("GO AUDIT missing mode")
    _log(f"GO AUDIT ok: bead_id={data.get('bead_id')}", verbose=verbose)
    return errors


def check_workflow_go_verify(verbose: bool) -> list[str]:
    errors: list[str] = []
    proc = subprocess.run(
        [PYTHON, str(REPO / "scripts" / "workflow_go.py"), "GO VERIFY"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if proc.returncode != 0 and "no prior workflow run" not in (proc.stdout + proc.stderr):
        errors.append(f"workflow_go GO VERIFY failed: {proc.stderr[:300]}")
        return errors
    if proc.returncode == 0:
        data = json.loads(proc.stdout.strip())
        if "git_pipeline" not in data:
            errors.append("GO VERIFY missing git_pipeline (post-intake integration)")
        _log("GO VERIFY ok", verbose=verbose)
    else:
        _log("GO VERIFY skipped (no prior run log)", verbose=verbose)
    return errors


def check_two_log_audit(verbose: bool) -> list[str]:
    errors: list[str] = []
    for rel in (
        "07_LOGS_AND_AUDIT/execution/execution.jsonl",
        "07_LOGS_AND_AUDIT/traces/traces.jsonl",
        "07_LOGS_AND_AUDIT/decisions/decision_log.jsonl",
        "docs/workflows/TWO_LOG_AUDIT.md",
    ):
        if not (REPO / rel).is_file():
            errors.append(f"missing two-log artifact: {rel}")
    _log("two-log paths ok", verbose=verbose)
    return errors


def check_auto_intake_cli(verbose: bool) -> list[str]:
    errors: list[str] = []
    proc = subprocess.run(
        [PYTHON, str(REPO / "scripts" / "auto_intake.py"), "--dry-run", "--limit", "1"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        errors.append(f"auto_intake CLI failed: {proc.stderr[:300]}")
        return errors
    data = json.loads(proc.stdout.strip())
    if "processed" not in data:
        errors.append("auto_intake output missing processed count")
    _log(f"auto_intake CLI ok: {data}", verbose=verbose)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate intake close-loop")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    all_errors: list[str] = []
    all_errors.extend(check_schema_and_decompose(args.verbose))
    all_errors.extend(check_two_log_audit(args.verbose))
    all_errors.extend(check_auto_intake_cli(args.verbose))
    all_errors.extend(check_workflow_go_audit(args.verbose))
    all_errors.extend(check_workflow_go_verify(args.verbose))

    with tempfile.TemporaryDirectory() as tmp:
        q = Path(tmp) / "intake_queue.jsonl"
        all_errors.extend(check_drain_dry_run(q, args.verbose))

    if all_errors:
        print("INTAKE LOOP VALIDATION FAILED", file=sys.stderr)
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("Intake close-loop validation OK")
    print("  queue schema -> auto_intake (dry-run) -> workflow_go GO AUDIT/VERIFY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
