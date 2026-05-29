#!/usr/bin/env python3
"""Publish one mission event to file store + optional Redis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from console_api.event_store import MissionEventHub  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--type", default="magnet_event")
    parser.add_argument("--data", default="{}")
    args = parser.parse_args()

    data = json.loads(args.data)
    hub = MissionEventHub()
    result = hub.publish(
        args.mission_id,
        {
            "type": args.type,
            "mission_id": args.mission_id,
            "timestamp": int(__import__("time").time() * 1000),
            "data": data,
        },
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
