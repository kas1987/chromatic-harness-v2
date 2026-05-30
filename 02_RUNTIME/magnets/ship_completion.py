"""Deterministic /ship-idea completion check (Stage 8 lean + Stage 10 live + DoD).

Closes the alignment gap documented in
``docs/operations/SESSION_LIFECYCLE_AUTOMATION_ALIGNMENT.md`` (Gap C): the closeout
phase never enforced /ship-idea's two non-skippable gates. This module turns the
evidence those stages emit into a yes/no the ``ClosureMagnet`` can act on — with no
extra agent turns.

Evidence is sourced from the magnet ``signal`` dict in two ways:

1. **Explicit flags** — ``lean_ok`` / ``live_ok`` / ``dod_ok`` (booleans). When present
   they win; this lets a caller that already evaluated the gates pass the verdict.
2. **Log scan** — ``ship_log`` (str): the session/ship log text. The checker scans it
   for the markers /ship-idea writes:
     * Stage 8: ``[S8-LEAN]`` with no *unjustified* WARN.
     * Stage 10: ``[S10-LIVE]`` carrying non-empty ``wired=`` and ``proof=``.
   When ``bead_id`` is given, only marker lines mentioning that bead are considered.

If neither flags nor a log are supplied the result is ``applicable=False`` — callers
should preserve legacy behavior rather than block (avoids false "incomplete" on
sessions that never went through /ship-idea).
"""

from __future__ import annotations

import re
from typing import Any

_S8 = "[S8-LEAN]"
_S10 = "[S10-LIVE]"
_WIRED = re.compile(r"wired=(\S+)")
_PROOF = re.compile(r"proof=(\S+)")
_EMPTY = {"", "<>", "<where>", "<log", "none", "todo", "tbd", "pending"}


def _lines_for(text: str, marker: str, bead_id: str = "") -> list[str]:
    out = []
    for raw in (text or "").splitlines():
        if marker not in raw:
            continue
        if bead_id and bead_id not in raw:
            continue
        out.append(raw.strip())
    return out


def _scan_lean(text: str, bead_id: str = "") -> bool:
    lines = _lines_for(text, _S8, bead_id)
    if not lines:
        return False
    # Lean passes when at least one marker line has no bare/unjustified WARN.
    for line in lines:
        low = line.lower()
        if "warn" not in low or "justified" in low:
            return True
    return False


def _scan_live(text: str, bead_id: str = "") -> bool:
    for line in _lines_for(text, _S10, bead_id):
        w = _WIRED.search(line)
        p = _PROOF.search(line)
        if not (w and p):
            continue
        if w.group(1).lower() in _EMPTY or p.group(1).lower() in _EMPTY:
            continue
        return True
    return False


def check_ship_completion(signal: dict[str, Any]) -> dict[str, Any]:
    """Evaluate /ship-idea Stage 8 + Stage 10 + DoD evidence in ``signal``.

    Returns a dict: ``applicable``, ``complete``, ``lean_ok``, ``live_ok``,
    ``dod_ok``, ``missing`` (list of stage labels), ``bead_id``.
    """
    bead_id = str(signal.get("bead_id") or signal.get("task_id") or "").strip()
    log = signal.get("ship_log") or signal.get("session_log") or ""

    has_flags = any(signal.get(k) is not None for k in ("lean_ok", "live_ok", "dod_ok"))
    applicable = bool(has_flags or log)

    def _flag(name: str, scanner) -> bool:
        if signal.get(name) is not None:
            return bool(signal.get(name))
        return scanner(log, bead_id) if log else False

    lean_ok = _flag("lean_ok", _scan_lean)
    live_ok = _flag("live_ok", _scan_live)
    # DoD has no marker convention yet — require an explicit flag; absent => not satisfied.
    dod_ok = bool(signal.get("dod_ok")) if signal.get("dod_ok") is not None else False

    missing: list[str] = []
    if not lean_ok:
        missing.append("S8-lean")
    if not live_ok:
        missing.append("S10-live")
    if not dod_ok:
        missing.append("DoD")

    return {
        "applicable": applicable,
        "complete": applicable and not missing,
        "lean_ok": lean_ok,
        "live_ok": live_ok,
        "dod_ok": dod_ok,
        "missing": missing,
        "bead_id": bead_id,
    }
