#!/usr/bin/env python3
"""Subscribe to Redis mission events and fan out to Console API instances.

Usage:
  set REDIS_URL=redis://localhost:6379/0
  set CONSOLE_INSTANCE_URLS=http://localhost:3030,http://localhost:3031
  python scripts/ws_redis_fanout.py

Each instance should expose POST /internal/events (ConsoleServer.handleIngestEvent).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib import request

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from console_api.event_store import RedisEventBus  # noqa: E402


def _instances() -> list[str]:
    raw = os.environ.get("CONSOLE_INSTANCE_URLS", "http://localhost:3030")
    return [u.strip().rstrip("/") for u in raw.split(",") if u.strip()]


def _post(url: str, event: dict) -> None:
    body = json.dumps(event).encode("utf-8")
    req = request.Request(
        f"{url}/internal/events",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=5) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"fanout failed {url}: HTTP {resp.status}")


def main() -> int:
    bus = RedisEventBus()
    if not bus.enabled:
        print("REDIS_URL not set — nothing to fan out", file=sys.stderr)
        return 1

    instances = _instances()
    print(f"Fanout to {len(instances)} instance(s); subscribing chromatic:mission:all")

    def handler(event: dict) -> None:
        mission_id = event.get("mission_id", "")
        if not mission_id:
            return
        for base in instances:
            try:
                _post(base, event)
            except Exception as exc:
                print(f"fanout error {base}: {exc}", file=sys.stderr)

    # Global channel subscription (publish with mission_id in payload)
    try:
        import redis

        client = redis.from_url(bus.url, decode_responses=True)
        pubsub = client.pubsub(ignore_subscribe_messages=True)
        pubsub.psubscribe("chromatic:mission:*")
        for message in pubsub.listen():
            if message.get("type") != "pmessage":
                continue
            try:
                data = json.loads(message["data"])
            except json.JSONDecodeError:
                continue
            handler(data)
    except KeyboardInterrupt:
        print("stopped")
    except ImportError:
        print("pip install redis", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
