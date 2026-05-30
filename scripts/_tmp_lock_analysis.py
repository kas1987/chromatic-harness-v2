#!/usr/bin/env python3
"""One-shot lock wait analysis — delete after use."""

import json
from pathlib import Path

LOG = Path("docs/workflows/WORKFLOW_RUN_LOG.jsonl")
events = []
for line in LOG.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    if d.get("event_type") != "lock.acquire":
        continue
    events.append(
        (
            d.get("lock_wait_ms", 0),
            d.get("timestamp", ""),
            d.get("lock_name", ""),
            d.get("lock_owner", ""),
        )
    )

events.sort(reverse=True)
high = [e for e in events if e[0] > 400]
print(f"Total lock.acquire events: {len(events)}")
print(f"High-wait (>400ms): {len(high)}")
print("\nTop 15 slowest:")
for w, ts, lock, owner in events[:15]:
    print(f"  {w:7}ms  {lock:<30}  {owner:<30}  {ts[:19]}")
