"""Session lifecycle telemetry (bead chromatic-harness-v2 telemetry P0).

Closes the brand-new-session cold-start gap: a fresh session emits a
`session.boot` event to the two-log audit spine immediately at SessionStart —
even with no prior handoff and no workflow activity — and a `session.end`
event at close. This makes every session observable from its first moment, and
distinguishes a true cold start (no handoff) from a warm resume.

Pure + fail-open: telemetry must never break session start/close, so all
emission is wrapped and returns the written paths (or an error dict) instead of
raising.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .two_log import TwoLogAudit


def _session_id() -> str:
    # Prefer the runner-provided id so boot/end correlate; else synthesize.
    return (
        os.environ.get("CLAUDE_SESSION_ID")
        or os.environ.get("CHROMATIC_SESSION_ID")
        or uuid.uuid4().hex
    )


def emit_session_event(
    event: str,
    repo_root: Path | None = None,
    *,
    cold_start: bool | None = None,
    invoked_by: str = "session_start",
    extra: dict[str, Any] | None = None,
    audit: TwoLogAudit | None = None,
) -> dict[str, Any]:
    """Emit a session lifecycle event to execution + trace logs. Never raises."""
    try:
        log = audit or TwoLogAudit(repo_root)
        sid = _session_id()
        payload: dict[str, Any] = {
            "event_type": event,  # e.g. "session.boot" / "session.end"
            "session_id": sid,
            "invoked_by": invoked_by,
            "agent_role": "session",
        }
        if cold_start is not None:
            payload["cold_start"] = cold_start
        if extra:
            payload.update(extra)
        exec_path = log.append_execution(payload)
        log.append_trace_span(
            {
                "name": event,
                "kind": "INTERNAL",
                "status": "OK",
                "duration_ms": 0,
                "attributes": {
                    "gen_ai.operation.name": "session",
                    "session.id": sid,
                    "session.event": event,
                    "session.cold_start": bool(cold_start),
                    "session.invoked_by": invoked_by,
                },
            }
        )
        return {"ok": True, "session_id": sid, "execution": str(exec_path)}
    except Exception as exc:  # fail-open: telemetry never blocks the session
        return {"ok": False, "error": str(exc)}


def emit_session_boot(
    repo_root: Path | None = None,
    *,
    cold_start: bool | None = None,
    invoked_by: str = "session_start",
    extra: dict[str, Any] | None = None,
    audit: TwoLogAudit | None = None,
) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).isoformat()
    merged = {"boot_ts": ts, **(extra or {})}
    return emit_session_event(
        "session.boot",
        repo_root,
        cold_start=cold_start,
        invoked_by=invoked_by,
        extra=merged,
        audit=audit,
    )


def emit_session_end(
    repo_root: Path | None = None,
    *,
    invoked_by: str = "session_closeout",
    extra: dict[str, Any] | None = None,
    audit: TwoLogAudit | None = None,
) -> dict[str, Any]:
    return emit_session_event(
        "session.end",
        repo_root,
        invoked_by=invoked_by,
        extra=extra,
        audit=audit,
    )
