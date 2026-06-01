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
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in active writers file: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Active writers file must be a JSON object, got {type(data).__name__}")
    writers = data.get("writers", [])
    by_file: dict[str, list[dict]] = defaultdict(list)
    for writer in writers:
        for file_path in writer.get("files_claimed", []):
            # Normalize path separators so ./src/foo.py and src/foo.py collide correctly
            normalized = Path(file_path).as_posix().lstrip("./") if file_path else file_path
            by_file[normalized].append(writer)
    collisions = {file_path: items for file_path, items in by_file.items() if len(items) > 1}
    if not collisions:
        print("No collisions detected.")
        return
    print("Collisions detected:")
    for file_path, items in collisions.items():
        print(f"\n- {file_path}")
        for item in items:
            print(
                f"  - writer={item.get('writer')} surface={item.get('surface')} session={item.get('session_id')} task={item.get('task')}"
            )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
