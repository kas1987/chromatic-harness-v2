"""Per-session loop-iteration guard (bead chromatic-harness-v2-ks05).

The router gate enforces per-dispatch cost, and budget/ledger.py tracks session
token burn — but nothing counted *repeated dispatches of the same task* within a
session. That is the runaway-loop / cache-read-amplification vector behind the
original cost spike: a cheap-per-turn task fired hundreds of times.

This tracks how many times a given task signature has been dispatched in the
current session and returns an escalating verdict:
  - ok    (<= warn threshold)
  - warn  (> warn, <= block) — advisory note added to routing output
  - block (> block) — gate denies; agent must change approach or hand off

Fail-open: any IO/parse error returns ok with count 0 (never blocks on a guard
malfunction). State lives in .agents/context/session_loop_counts.json, scoped to
the session id so a new session starts fresh.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

WARN_THRESHOLD = int(os.environ.get("ROUTER_LOOP_WARN", "10"))
BLOCK_THRESHOLD = int(os.environ.get("ROUTER_LOOP_BLOCK", "25"))


def _session_id() -> str:
    return (
        os.environ.get("CLAUDE_SESSION_ID")
        or os.environ.get("CHROMATIC_SESSION_ID")
        or "default"
    )


def task_signature(description: str, subagent_type: str = "") -> str:
    """Stable signature for a task: normalized description + agent type."""
    norm = re.sub(r"\s+", " ", (description or "").strip().lower())[:200]
    raw = f"{subagent_type}|{norm}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _state_path(repo_root: Path) -> Path:
    return repo_root / ".agents" / "context" / "session_loop_counts.json"


def _load(path: Path, session_id: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("session_id") == session_id:
            return data
    except Exception:
        pass
    return {"session_id": session_id, "counts": {}}


def bump_and_check(
    description: str,
    subagent_type: str = "",
    *,
    repo_root: Path | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Increment the dispatch count for this task and return a verdict. Fail-open."""
    try:
        repo = repo_root or Path(__file__).resolve().parents[2]
        sid = session_id or _session_id()
        path = _state_path(repo)
        state = _load(path, sid)
        sig = task_signature(description, subagent_type)
        counts = state.setdefault("counts", {})
        counts[sig] = int(counts.get(sig, 0)) + 1
        count = counts[sig]

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), encoding="utf-8")

        if count > BLOCK_THRESHOLD:
            level = "block"
        elif count > WARN_THRESHOLD:
            level = "warn"
        else:
            level = "ok"
        return {"ok": True, "count": count, "level": level, "signature": sig}
    except Exception as exc:  # fail-open
        return {"ok": False, "count": 0, "level": "ok", "error": str(exc)}


def advisory_note(verdict: dict[str, Any]) -> str:
    """Human-readable note for the routing advisory, or '' when ok."""
    level = verdict.get("level")
    count = verdict.get("count", 0)
    if level == "warn":
        return (
            f" | LOOP WARN: this task dispatched {count}x this session "
            f"(>{WARN_THRESHOLD}) — confirm progress, not a runaway loop"
        )
    if level == "block":
        return (
            f" | LOOP BLOCK: dispatched {count}x this session "
            f"(>{BLOCK_THRESHOLD}) — change approach or hand off (SOP)"
        )
    return ""
