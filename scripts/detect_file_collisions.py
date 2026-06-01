#!/usr/bin/env python3
"""Detect simple file collisions from .chromatic/active_writers.json."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--active-writers", default=".chromatic/active_writers.json")
    args = parser.parse_args()
    path = Path(args.active_writers)
    if not path.exists():
        raise SystemExit(f"Active writers file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    writers = data.get("writers", [])
    by_file: dict[str, list[dict]] = defaultdict(list)
    for writer in writers:
        for file_path in writer.get("files_claimed", []):
            by_file[file_path].append(writer)
    collisions = {file_path: items for file_path, items in by_file.items() if len(items) > 1}
    if not collisions:
        print("No collisions detected.")
        return
    print("Collisions detected:")
    for file_path, items in collisions.items():
        print(f"\n- {file_path}")
        for item in items:
            print(f"  - writer={item.get('writer')} surface={item.get('surface')} session={item.get('session_id')} task={item.get('task')}")
    raise SystemExit(2)


if __name__ == "__main__":
    main()
