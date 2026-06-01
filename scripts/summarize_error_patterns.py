#!/usr/bin/env python3
"""Summarize repeated Chromatic Harness event patterns."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_events(path: Path) -> list[dict]:
    events = []
    if not path.exists():
        return events
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                events.append(json.loads(line))
    return events


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="00_META/observability/ERROR_LOG.jsonl")
    parser.add_argument("--min-count", type=int, default=1)
    args = parser.parse_args()
    events = load_events(Path(args.log))
    by_category = Counter(e.get("category", "unknown") for e in events)
    by_severity = Counter(e.get("severity", "unknown") for e in events)
    by_signature = Counter(e.get("error_signature") or e.get("message", "")[:80] for e in events)
    files = defaultdict(int)
    for event in events:
        for file_path in event.get("files_touched") or []:
            files[file_path] += 1

    print("# Error Pattern Summary\n")
    print("## By Severity")
    for key, count in by_severity.most_common():
        print(f"- {key}: {count}")
    print("\n## By Category")
    for key, count in by_category.most_common():
        print(f"- {key}: {count}")
    print("\n## Repeated Signatures")
    for key, count in by_signature.most_common():
        if count >= args.min_count:
            print(f"- {count}x: {key}")
    print("\n## Files Most Often Touched By Events")
    for key, count in sorted(files.items(), key=lambda item: item[1], reverse=True)[:20]:
        print(f"- {count}x: {key}")


if __name__ == "__main__":
    main()
