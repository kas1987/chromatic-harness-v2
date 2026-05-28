#!/usr/bin/env python3
"""Small file-backed state helper for conditional hook chains.

Hooks in Claude-style runtimes are event-driven, not dependency-driven. This
module lets one hook set a short-lived state marker that a later hook can read
before deciding whether to act.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

STATE_DIR = Path(os.getenv("HOOK_STATE_DIR", ".state/hooks"))
DEFAULT_TTL_SECONDS = int(os.getenv("HOOK_CHAIN_TTL_SECONDS", "120"))


def now_seconds() -> int:
    return int(time.time())


def safe_part(value: str) -> str:
    return (
        value.replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace(" ", "_")
    )


def state_path(session_id: str, chain: str) -> Path:
    return STATE_DIR / f"{safe_part(session_id)}.{safe_part(chain)}.json"


def load_state(session_id: str, chain: str) -> Optional[Dict[str, Any]]:
    path = state_path(session_id, chain)
    if not path.exists():
        return None

    state = json.loads(path.read_text(encoding="utf-8"))
    expires_at = state.get("expires_at_epoch")

    if expires_at is not None and now_seconds() > int(expires_at):
        clear_state(session_id, chain)
        return None

    return state


def save_state(session_id: str, chain: str, state: Dict[str, Any]) -> Dict[str, Any]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    current_time = now_seconds()
    state.setdefault("session_id", session_id)
    state.setdefault("chain", chain)
    state.setdefault("created_at_epoch", current_time)
    state.setdefault("expires_at_epoch", current_time + DEFAULT_TTL_SECONDS)
    state["updated_at_epoch"] = current_time

    path = state_path(session_id, chain)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)
    return state


def clear_state(session_id: str, chain: str) -> bool:
    path = state_path(session_id, chain)
    if path.exists():
        path.unlink()
        return True
    return False


def reset_state(session_id: str, chain: str, stage: int = 0) -> Dict[str, Any]:
    return save_state(session_id, chain, {"stage": stage, "reset": True})
