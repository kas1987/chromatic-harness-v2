#!/usr/bin/env python3
"""Hook 1: detect a chain trigger and set stage 1 state."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import os

from chain_state import save_state  # noqa: E402

CHAIN = "permission_followup_autopilot"
TRIGGER_EVENTS = {"PermissionRequest", "Notification", "UserPromptSubmit"}


def _try_audit(session_id: str, event_name: str) -> None:
    try:
        import argparse
        from audit_log import DEFAULT_LOG_PATH, append_event, build_event

        args = argparse.Namespace(
            event_type="hook_chain_triggered",
            event_id=None,
            timestamp=None,
            severity="info",
            source_repo=os.getenv("AGENTOPS_SOURCE_REPO", "kas1987/claude-config"),
            source_component="hooks.hook_chain_detect",
            agent_id=os.getenv("AGENTOPS_AGENT_ID"),
            session_id=session_id,
            task_id=os.getenv("AGENTOPS_TASK_ID"),
            run_id=os.getenv("AGENTOPS_RUN_ID"),
            parent_event_id=None,
            duration_ms=None,
        )
        append_event(
            build_event(args, {"chain": CHAIN, "trigger_event": event_name}),
            Path(os.getenv("AGENTOPS_LOG_PATH", str(DEFAULT_LOG_PATH))),
        )
    except Exception:
        pass


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
    event_name = event_name_from(payload)

    if event_name not in TRIGGER_EVENTS:
        return 0

    session_id = session_id_from(payload)
    save_state(
        session_id,
        CHAIN,
        {
            "stage": 1,
            "hook_1_fired": True,
            "hook_2_fired": False,
            "hook_3_fired": False,
            "event_name": event_name,
            "tool_name": payload.get("tool_name"),
            "cwd": payload.get("cwd"),
            "permission_mode": payload.get("permission_mode"),
        },
    )
    _try_audit(session_id, event_name)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
