#!/usr/bin/env python3
"""Log a bounded agent activity event (workflow + two-log + optional intake).

Usage:
  python scripts/log_agent_activity.py log --event phase.complete --bead-id chromatic-harness-v2-abc --lane agent --summary "Done"
  python scripts/log_agent_activity.py log --event git.failed --lane human --error "push rejected" --intake
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from activity.log import log_activity  # noqa: E402


def cmd_log(args: argparse.Namespace) -> int:
    result = log_activity(
        REPO,
        event_type=args.event,
        bead_id=args.bead_id or "",
        lane=args.lane,
        decision=args.decision or "",
        summary=args.summary or "",
        error=args.error or "",
        agent_role=args.agent_role,
        intake_on_failure=args.intake,
        enqueue_intake=args.enqueue_intake,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Log harness agent activity")
    sub = parser.add_subparsers(dest="command", required=True)
    log_p = sub.add_parser("log", help="Append activity event")
    log_p.add_argument("--event", required=True, help="e.g. phase.complete, session.boot")
    log_p.add_argument("--bead-id", default="")
    log_p.add_argument("--lane", choices=["agent", "human", "review"], default="agent")
    log_p.add_argument("--decision", default="")
    log_p.add_argument("--summary", default="")
    log_p.add_argument("--error", default="")
    log_p.add_argument("--agent-role", default="orchestrator")
    log_p.add_argument(
        "--intake",
        action="store_true",
        help="Enqueue intake on failure (error required)",
    )
    log_p.add_argument(
        "--enqueue-intake",
        action="store_true",
        help="Always enqueue intake follow_up",
    )
    args = parser.parse_args()
    if args.command == "log":
        return cmd_log(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
