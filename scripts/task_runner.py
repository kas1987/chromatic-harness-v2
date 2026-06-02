#!/usr/bin/env python3
"""task_runner.py (CLI) — start the long-running next-task supervisor.

Thin wrapper over 02_RUNTIME/orchestrator/task_runner.py. See
docs/superpowers/specs/2026-06-02-long-running-task-runner-design.md.

Examples:
  # Validate selection + confidence on the live queue (no claim, no merge):
  python scripts/task_runner.py --once --dry-run --json

  # Run one bead end to end (claim -> worker -> CI -> merge -> close):
  python scripts/task_runner.py --once --epic chromatic-harness-v2-u8uj

  # Long-running loop until the queue drains or a guard trips:
  python scripts/task_runner.py --loop --epic chromatic-harness-v2-u8uj --max-usd 10 --on-breach pause

Kill-switch: create 07_LOGS_AND_AUDIT/task_runner/STOP or set TASK_RUNNER_STOP=1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "02_RUNTIME") not in sys.path:
    sys.path.insert(0, str(REPO / "02_RUNTIME"))

from orchestrator.task_runner import (  # noqa: E402
    Outcome,
    RunnerConfig,
    TaskRunner,
    import_error,
)


def build_config(args: argparse.Namespace) -> RunnerConfig:
    return RunnerConfig(
        scope=args.scope,
        epic=args.epic,
        t_level=args.t_level,
        max_t_level=args.max_t_level,
        max_iterations=args.max_iterations,
        max_usd=args.max_usd,
        max_tokens=args.max_tokens,
        on_breach=args.on_breach,
        max_consecutive_failures=args.max_consecutive_failures,
        auto_merge=not args.no_auto_merge,
        dry_run=args.dry_run,
        worker_timeout=args.worker_timeout,
        ci_timeout=args.ci_timeout,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Long-running next-task supervisor (bead xab3)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run a single iteration and exit")
    mode.add_argument("--loop", action="store_true", help="Run until queue drains / guard trips (default)")

    ap.add_argument("--scope", choices=["single-bead", "epic", "area"], default="epic")
    ap.add_argument("--epic", default="", help="Epic-id prefix filter when --scope epic")
    ap.add_argument(
        "--t-level",
        choices=["T1", "T2", "T3"],
        default="T3",
        help="Per-task T-level handed to the delegate gate (T4 is never autonomous)",
    )
    ap.add_argument("--max-t-level", choices=["T1", "T2", "T3"], default="T3")
    ap.add_argument("--max-iterations", type=int, default=25)
    ap.add_argument("--max-usd", type=float, default=10.0, help="Spend ceiling (0 = inherit/none)")
    ap.add_argument("--max-tokens", type=int, default=0, help="Token ceiling (0 = none)")
    ap.add_argument("--on-breach", choices=["pause", "handoff", "halt"], default="pause")
    ap.add_argument("--max-consecutive-failures", type=int, default=3)
    ap.add_argument("--no-auto-merge", action="store_true", help="Implement -> PR but do not squash-merge/close")
    ap.add_argument("--dry-run", action="store_true", help="Score + decide only; never claim, dispatch, or merge")
    ap.add_argument("--worker-timeout", type=int, default=1800)
    ap.add_argument("--ci-timeout", type=int, default=1800)
    ap.add_argument("--json", action="store_true", help="Print full JSON results")
    args = ap.parse_args()

    err = import_error()
    if err is not None:
        print(json.dumps({"ok": False, "error": f"go_mode unavailable: {err}"}, indent=2))
        return 1

    runner = TaskRunner(build_config(args))

    if args.once:
        result = runner.run_once()
        runner._write_latest(result)  # surface the single-iteration artifact
        payload = result.to_dict()
        print(json.dumps(payload, indent=2) if args.json else _line(result))
        return 0 if result.outcome != Outcome.HALT else 2

    results = runner.run_loop()
    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        for r in results:
            print(_line(r))
        counts: dict[str, int] = {}
        for r in results:
            counts[r.outcome.value] = counts.get(r.outcome.value, 0) + 1
        print(f"-- {len(results)} iterations: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 0


def _line(r) -> str:
    conf = f"{r.confidence:.1f}" if r.confidence is not None else "--"
    pr = f" PR#{r.pr_number}" if r.pr_number else ""
    return f"[{r.outcome.value:9}] {r.bead_id or '-':<28} conf={conf:>5} band={r.band or '-'}{pr}  {r.detail}"


if __name__ == "__main__":
    raise SystemExit(main())
