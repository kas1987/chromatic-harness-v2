#!/usr/bin/env python3
"""Hook 3: reset or clear hook-chain state after completion/end of turn."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from chain_state import clear_state, load_state, save_state  # noqa: E402


def _try_audit(session_id: str, event_name: str) -> None:
    try:
        import argparse
        from audit_log import DEFAULT_LOG_PATH, append_event, build_event

        args = argparse.Namespace(
            event_type="hook_chain_reset",
            event_id=None,
            timestamp=None,
            severity="info",
            source_repo=os.getenv("AGENTOPS_SOURCE_REPO", "kas1987/claude-config"),
            source_component="hooks.hook_chain_reset",
            agent_id=os.getenv("AGENTOPS_AGENT_ID"),
            session_id=session_id,
            task_id=os.getenv("AGENTOPS_TASK_ID"),
            run_id=os.getenv("AGENTOPS_RUN_ID"),
            parent_event_id=None,
            duration_ms=None,
        )
        append_event(
            build_event(args, {"chain": CHAIN, "reset_event": event_name}),
            Path(os.getenv("AGENTOPS_LOG_PATH", str(DEFAULT_LOG_PATH))),
        )
    except Exception:
        pass


CHAIN = "permission_followup_autopilot"
RESET_EVENTS = {"PostToolUse", "Stop", "SessionEnd", "PostToolUseFailure"}


def session_id_from(payload: dict) -> str:
    return str(payload.get("session_id") or payload.get("transcript_path") or "unknown-session")


def event_name_from(payload: dict) -> str:
    return str(
        payload.get("hook_event_name")
        or payload.get("hookEventName")
        or payload.get("event_name")
        or ""
    )


def main() -> int:
    payload = json.load(sys.stdin)
    session_id = session_id_from(payload)
    event_name = event_name_from(payload)
    state = load_state(session_id, CHAIN)

    if not state:
        return 0

    if event_name in RESET_EVENTS:
        clear_state(session_id, CHAIN)
        _try_audit(session_id, event_name)
        return 0

    if state.get("stage") not in {0, 1, 2}:
        state["stage"] = 1
        state["hook_3_fired"] = True
        save_state(session_id, CHAIN, state)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
