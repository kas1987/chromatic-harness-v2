#!/usr/bin/env python3
"""deadlock_detector.py — deadlock detection (P1-CC-008 / ju0o.7).

Builds a wait-for graph from the active-lease ledger plus a set of pending
resource requests, then detects circular waits (A waits on B, B waits on A, …).
When a cycle is found an escalation record is emitted to the collision audit
trail so a human / supervisor agent can break the deadlock.

A wait edge ``requester -> holder`` exists when an agent requests a resource that
overlaps a resource already held by an active write/exclusive lease owned by a
*different* agent.

Wraps lease_manager.py — reuses the active_leases ledger + overlaps().

Usage:
    # requests file: JSON list of {"agent": "...", "resource": "scripts/foo.py"}
    python scripts/deadlock_detector.py detect --requests requests.json
    python scripts/deadlock_detector.py summarize
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import lease_manager as _lm  # noqa: E402

DEFAULT_LEDGER = _lm.DEFAULT_LEDGER
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "collision"
ESCALATION_PATH = ARTIFACT_DIR / "deadlock_latest.json"
WRITE_MODES = {"write", "exclusive"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_wait_graph(
    requests: list[dict[str, str]],
    ledger: Path | None = None,
) -> dict[str, set[str]]:
    """Construct an agent->agents wait-for graph.

    *requests* is a list of {"agent", "resource"} that agents are blocked on.
    An edge requester->holder is added when the requested resource overlaps a
    resource held by an active write/exclusive lease of a different agent.
    """
    ledger = ledger or DEFAULT_LEDGER
    holders: list[tuple[str, str]] = []  # (resource, owner_agent)
    for r in _lm.load_ledger(ledger):
        if not _lm.is_active(r):
            continue
        if r.get("mode") not in WRITE_MODES:
            continue
        owner = r.get("owner_agent")
        for res in r.get("resources", []):
            holders.append((res, owner))

    graph: dict[str, set[str]] = {}
    for req in requests:
        requester = req.get("agent")
        resource = req.get("resource", "")
        for held_res, owner in holders:
            if owner == requester:
                continue
            if _lm.overlaps(resource, held_res):
                graph.setdefault(requester, set()).add(owner)
    return graph


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Return all simple cycles in the directed wait-for *graph* (DFS)."""
    cycles: list[list[str]] = []
    seen_signatures: set[frozenset[str]] = set()

    def dfs(node: str, stack: list[str], on_stack: set[str]) -> None:
        for nxt in sorted(graph.get(node, ())):
            if nxt in on_stack:
                idx = stack.index(nxt)
                cycle = stack[idx:]
                sig = frozenset(cycle)
                if sig not in seen_signatures:
                    seen_signatures.add(sig)
                    cycles.append(cycle)
                continue
            dfs(nxt, stack + [nxt], on_stack | {nxt})

    for start in sorted(graph):
        dfs(start, [start], {start})
    return cycles


def detect_deadlocks(
    requests: list[dict[str, str]],
    ledger: Path | None = None,
    *,
    write_escalation: bool = True,
) -> dict[str, Any]:
    """Detect circular waits and emit an escalation record if any are found."""
    graph = build_wait_graph(requests, ledger)
    cycles = find_cycles(graph)
    result: dict[str, Any] = {
        "status": "deadlock" if cycles else "ok",
        "detected_at": _now_iso(),
        "cycle_count": len(cycles),
        "cycles": cycles,
        "escalated": False,
    }
    if cycles and write_escalation:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        ESCALATION_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["escalated"] = True
    return result


def summarize(ledger: Path | None = None) -> dict[str, Any]:
    """Fail-open summary; no pending requests known here, so reports graph health."""
    try:
        # Without live requests we cannot infer waits; report holder count only.
        holders = 0
        for r in _lm.load_ledger(ledger or DEFAULT_LEDGER):
            if _lm.is_active(r) and r.get("mode") in WRITE_MODES:
                holders += len(r.get("resources", []))
        return {"status": "ok", "active_write_resources": holders}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "active_write_resources": None}


def main() -> int:
    parser = argparse.ArgumentParser(description="Deadlock detection (P1-CC-008)")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("detect")
    d.add_argument("--requests", required=True, help="JSON file: [{agent, resource}, ...]")

    sub.add_parser("summarize")

    args = parser.parse_args()
    ledger = Path(args.ledger)

    if args.command == "detect":
        requests = json.loads(Path(args.requests).read_text(encoding="utf-8"))
        result = detect_deadlocks(requests, ledger)
        print(json.dumps(result, indent=2))
        return 2 if result["status"] == "deadlock" else 0

    if args.command == "summarize":
        print(json.dumps(summarize(ledger), indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
