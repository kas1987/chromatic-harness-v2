#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict
from common_harness import read_json, repo_root


def main():
    ap = argparse.ArgumentParser(description="Detect active writer collisions")
    ap.add_argument("--repo-root")
    ap.add_argument("--active-writers", default=".chromatic/active_writers.json")
    args = ap.parse_args()
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    path = Path(args.active_writers)
    path = path if path.is_absolute() else root / path
    data = read_json(path, {"claims": {}})
    collisions = []
    if not isinstance(data, dict):
        print(f"malformed active-writers file (not a JSON object): {path}", file=sys.stderr)
        return 2
    claims = data.get("claims", {})
    if isinstance(claims, dict):
        for f, cur in claims.items():
            if isinstance(cur, list) and len(cur) > 1:
                collisions.append((f, cur))
    seen = defaultdict(list)
    for w in data.get("writers", []):
        for f in w.get("files", []):
            seen[f].append(w)
    for f, ws in seen.items():
        if len({w.get("session") for w in ws}) > 1:
            collisions.append((f, ws))
    if collisions:
        print("COLLISIONS DETECTED", file=sys.stderr)
        print(json.dumps(collisions, indent=2), file=sys.stderr)
        return 1
    print("No active writer collisions detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
