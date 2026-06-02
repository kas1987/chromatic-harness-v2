#!/usr/bin/env python3
"""Reference collision checker for lease records and mutation manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def overlaps(a: str, b: str) -> bool:
    a = a.rstrip("/")
    b = b.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check for active lease collisions")
    parser.add_argument("--ledger", default="01_STATE/leases/active_leases.jsonl")
    args = parser.parse_args()
    records = [r for r in load_jsonl(Path(args.ledger)) if r.get("status") == "active" and r.get("mode") != "read"]
    collisions = []
    for i, left in enumerate(records):
        for right in records[i + 1 :]:
            for lres in left.get("resources", []):
                for rres in right.get("resources", []):
                    if overlaps(lres, rres):
                        collisions.append(
                            {
                                "left": left.get("lease_id"),
                                "right": right.get("lease_id"),
                                "resource_a": lres,
                                "resource_b": rres,
                            }
                        )
    print(json.dumps({"collision_count": len(collisions), "collisions": collisions}, indent=2))
    return 1 if collisions else 0


if __name__ == "__main__":
    raise SystemExit(main())
