#!/usr/bin/env python3
"""Small deterministic helper for updating Chromatic next-work.queue.json."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_QUEUE = "07_LOGS_AND_AUDIT/review_intake/queue.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_queue(path: Path) -> dict:
    if not path.exists() or not path.read_text().strip():
        return {"items": []}
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return {"items": data}
    data.setdefault("items", [])
    return data


def save_queue(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default=DEFAULT_QUEUE)
    parser.add_argument("--item", required=True, help="Path to next work item JSON")
    args = parser.parse_args()

    queue_path = Path(args.queue)
    item = json.loads(Path(args.item).read_text())
    queue = load_queue(queue_path)
    items = queue["items"]
    for idx, existing in enumerate(items):
        if existing.get("id") == item.get("id"):
            item["updated_at"] = now()
            items[idx] = {**existing, **item}
            save_queue(queue_path, queue)
            print(f"updated {item['id']}")
            return 0
    item["created_at"] = now()
    items.append(item)
    save_queue(queue_path, queue)
    print(f"created {item['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
