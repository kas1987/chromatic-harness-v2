#!/usr/bin/env python3
"""Append explicit learning usage outcomes for evidence-tier scoring."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOG_PATH = Path(
    os.environ.get("CHROMATIC_LEARNING_USAGE_LOG", "")
).resolve() if os.environ.get("CHROMATIC_LEARNING_USAGE_LOG") else (REPO / ".agents" / "metrics" / "learning_usage.jsonl")


def _slug(raw: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "-", str(raw or "").lower()).strip("-")
    return base[:90] or "learning"


def _clean_token(raw: str | None) -> str:
    s = str(raw or "").strip().strip('"').strip("'")
    if s in {"", ".", "./", ".\\"}:
        return ""
    return s


def main() -> int:
    parser = argparse.ArgumentParser(description="Log learning usage outcomes")
    parser.add_argument("--name", required=True, help="Learning name")
    parser.add_argument(
        "--event-type",
        required=True,
        choices=["applied_success", "applied_failure"],
        help="Outcome event type",
    )
    parser.add_argument("--rig-id", default="", help="Rig identifier")
    parser.add_argument("--learning-path", default="", help="Learning source path")
    parser.add_argument("--notes", default="", help="Optional notes")
    parser.add_argument("--confidence", type=float, default=None, help="Optional confidence snapshot")
    args = parser.parse_args()

    name = _clean_token(args.name)
    if not name:
        raise SystemExit("--name must be non-empty")

    event = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_type": args.event_type,
        "learning_name": name,
        "learning_slug": _slug(name),
    }

    rig_id = _clean_token(args.rig_id)
    if rig_id:
        event["rig_id"] = rig_id

    learning_path = _clean_token(args.learning_path).replace("\\", "/")
    if learning_path:
        event["learning_path"] = learning_path

    notes = _clean_token(args.notes)
    if notes:
        event["notes"] = notes

    if args.confidence is not None:
        event["confidence"] = max(0.0, min(1.0, float(args.confidence)))

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=True) + "\n")

    print(json.dumps({"ok": True, "log_path": str(LOG_PATH), "event": event}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
