#!/usr/bin/env python3
"""Backfill learning usage events from existing harvest catalog artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HARVEST_LATEST = REPO / ".agents" / "harvest" / "latest.json"
USAGE_LOG = REPO / ".agents" / "metrics" / "learning_usage.jsonl"


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _existing_backfill_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    if not path.is_file():
        return keys
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if str(row.get("notes") or "") != "backfill_from_harvest_latest":
            continue
        key = "|".join(
            [
                str(row.get("event_type") or ""),
                str(row.get("learning_path") or ""),
                str(row.get("rig_id") or ""),
                str(row.get("timestamp_utc") or ""),
            ]
        )
        keys.add(key)
    return keys


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill learning usage from harvest latest catalog")
    parser.add_argument("--write", action="store_true", help="Append events to usage log")
    args = parser.parse_args()

    harvest = _load_json(HARVEST_LATEST)
    promoted = harvest.get("promoted") if isinstance(harvest.get("promoted"), list) else []
    generated_at = str(harvest.get("generated_at") or "").strip()
    ts = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    seen = _existing_backfill_keys(USAGE_LOG)
    events: list[dict] = []
    for row in promoted:
        if not isinstance(row, dict):
            continue
        source = str(row.get("from") or "").strip()
        if not source:
            continue
        name = Path(source).stem
        event = {
            "timestamp_utc": ts,
            "event_type": "applied_success",
            "learning_name": name,
            "learning_path": source.replace("\\", "/"),
            "rig_id": str(row.get("rig_id") or ""),
            "notes": "backfill_from_harvest_latest",
        }
        key = "|".join(
            [
                str(event.get("event_type") or ""),
                str(event.get("learning_path") or ""),
                str(event.get("rig_id") or ""),
                str(event.get("timestamp_utc") or ""),
            ]
        )
        if key in seen:
            continue
        events.append(event)

    written = 0
    if args.write and events:
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with USAGE_LOG.open("a", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event, ensure_ascii=True) + "\n")
                written += 1

    print(
        json.dumps(
            {
                "source": str(HARVEST_LATEST),
                "usage_log": str(USAGE_LOG),
                "events_found": len(events),
                "events_written": written,
                "write": bool(args.write),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
