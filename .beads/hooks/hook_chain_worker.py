#!/usr/bin/env python3
"""Hook 2: only act when Hook 1 has set stage 1 state.

This hook does not blindly approve actions. Hook 1 only grants eligibility;
Hook 2 still applies a conservative safety check before allowing anything.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from chain_state import load_state, save_state  # noqa: E402


def _try_audit(session_id: str, event_type: str, tool_name: str, action: str) -> None:
    try:
        import argparse
        from audit_log import DEFAULT_LOG_PATH, append_event, build_event

        args = argparse.Namespace(
            event_type=event_type,
            event_id=None,
            timestamp=None,
            severity="info",
            source_repo=os.getenv("AGENTOPS_SOURCE_REPO", "kas1987/claude-config"),
            source_component="hooks.hook_chain_worker",
            agent_id=os.getenv("AGENTOPS_AGENT_ID"),
            session_id=session_id,
            task_id=os.getenv("AGENTOPS_TASK_ID"),
            run_id=os.getenv("AGENTOPS_RUN_ID"),
            parent_event_id=None,
            duration_ms=None,
        )
        append_event(
            build_event(args, {"chain": CHAIN, "tool": tool_name, "action": action}),
            Path(os.getenv("AGENTOPS_LOG_PATH", str(DEFAULT_LOG_PATH))),
        )
    except Exception:
        pass


CHAIN = "permission_followup_autopilot"
SAFE_BASH_PREFIXES = (
    "python -m pytest",
    "pytest",
    "git status",
    "git diff",
    "git log",
)


def session_id_from(payload: dict) -> str:
    return str(payload.get("session_id") or payload.get("transcript_path") or "unknown-session")


def emit_allow(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def main() -> int:
    payload = json.load(sys.stdin)
    session_id = session_id_from(payload)
    state = load_state(session_id, CHAIN)

    if not state:
        return 0

    if state.get("stage") != 1 or not state.get("hook_1_fired"):
        return 0

    tool_name = payload.get("tool_name") or payload.get("tool")
    tool_input = payload.get("tool_input") or payload.get("input") or {}

    if tool_name == "Bash":
        command = str(tool_input.get("command", "")).strip()
        if any(command.startswith(prefix) for prefix in SAFE_BASH_PREFIXES):
            state["stage"] = 2
            state["hook_2_fired"] = True
            state["last_tool_name"] = tool_name
            state["last_action"] = command
            save_state(session_id, CHAIN, state)
            emit_allow("Hook chain approved safe follow-up action after Hook 1 trigger.")
            _try_audit(session_id, "hook_chain_worker_allowed", tool_name or "", command)
            return 0

    # Unknown or unsafe action remains under normal permission flow.
    _try_audit(session_id, "hook_chain_worker_skipped", tool_name or "", "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
