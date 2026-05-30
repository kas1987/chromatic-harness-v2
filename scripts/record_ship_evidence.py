#!/usr/bin/env python3
"""Record /ship-idea completion evidence for the closeout Gap C check.

`/ship-idea` Stages 8/10 emit `[S8-LEAN]` and `[S10-LIVE]` log lines, but those are
agent text with no durable sink. This producer writes the structured equivalent to
`.agents/handoffs/ship_evidence.json`, which `session_closeout.evaluate_ship_completion`
consumes to decide whether a bead is safe to close.

File shape (per-bead keyed):
    { "<bead-id>": {"lean_ok": true, "live_ok": true, "dod_ok": true,
                     "ship_log": "<optional raw [S8]/[S10] text>"} }

Usage:
  python scripts/record_ship_evidence.py --bead-id chr-1 --lean-ok --live-ok --dod-ok
  python scripts/record_ship_evidence.py --bead-id chr-1 --ship-log "[S10-LIVE] wired=x proof=y"
  python scripts/record_ship_evidence.py --bead-id chr-1 --clear
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT = _REPO / ".agents" / "handoffs" / "ship_evidence.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def record_evidence(
    path: Path,
    *,
    bead_id: str,
    lean_ok: bool | None = None,
    live_ok: bool | None = None,
    dod_ok: bool | None = None,
    ship_log: str | None = None,
    clear: bool = False,
) -> dict[str, Any]:
    """Merge one bead's ship evidence into the JSON file. Returns the full mapping."""
    if not bead_id:
        raise ValueError("bead_id is required")
    data = _load(path)
    if clear:
        data.pop(bead_id, None)
    else:
        entry: dict[str, Any] = dict(data.get(bead_id) or {})
        if lean_ok is not None:
            entry["lean_ok"] = bool(lean_ok)
        if live_ok is not None:
            entry["live_ok"] = bool(live_ok)
        if dod_ok is not None:
            entry["dod_ok"] = bool(dod_ok)
        if ship_log is not None:
            entry["ship_log"] = ship_log
        data[bead_id] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return data


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Record /ship-idea completion evidence")
    p.add_argument("--bead-id", required=True)
    p.add_argument("--lean-ok", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--live-ok", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--dod-ok", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--ship-log", default=None)
    p.add_argument("--clear", action="store_true")
    p.add_argument("--path", default="")
    args = p.parse_args(argv)

    path = Path(args.path) if args.path else _DEFAULT
    data = record_evidence(
        path,
        bead_id=args.bead_id,
        lean_ok=args.lean_ok,
        live_ok=args.live_ok,
        dod_ok=args.dod_ok,
        ship_log=args.ship_log,
        clear=args.clear,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "path": str(path),
                "bead": args.bead_id,
                "entry": data.get(args.bead_id, "(cleared)"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
