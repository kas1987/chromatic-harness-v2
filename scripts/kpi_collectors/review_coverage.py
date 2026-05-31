#!/usr/bin/env python3
"""KPI collector: review coverage for KOS Stage 6.

Reads .agents/reviews/ and .agents/candidates/ to compute:
  - reviewed_pct: percentage of non-schema candidates that have a review record
  - auto_approved: count of reviews with reviewer == "auto" and verdict == "approved"
  - human_reviewed: count of reviews with reviewer == "human"

Emits: {"reviewed_pct": float, "auto_approved": int, "human_reviewed": int, "status": "ok"}
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CANDIDATES_DIR = REPO / ".agents" / "candidates"
REVIEWS_DIR = REPO / ".agents" / "reviews"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta


def main() -> int:
    # Count total candidates (excluding SCHEMA.md and underscore files)
    total_candidates = 0
    if CANDIDATES_DIR.is_dir():
        for path in CANDIDATES_DIR.iterdir():
            if (
                path.suffix == ".md"
                and path.name not in ("SCHEMA.md",)
                and not path.name.startswith("_")
            ):
                total_candidates += 1

    # Read all review JSON files
    reviewed_names: set[str] = set()
    auto_approved = 0
    human_reviewed = 0

    if REVIEWS_DIR.is_dir():
        for path in REVIEWS_DIR.iterdir():
            if path.suffix != ".json":
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except (OSError, json.JSONDecodeError):
                continue

            candidate = data.get("candidate", "")
            if candidate:
                reviewed_names.add(candidate)

            reviewer = data.get("reviewer", "")
            verdict = data.get("verdict", "")

            if reviewer == "auto" and verdict == "approved":
                auto_approved += 1
            elif reviewer == "human":
                human_reviewed += 1

    reviewed_count = len(reviewed_names)
    reviewed_pct = (
        round(reviewed_count / total_candidates * 100, 1)
        if total_candidates > 0
        else 0.0
    )

    result = {
        "reviewed_pct": reviewed_pct,
        "auto_approved": auto_approved,
        "human_reviewed": human_reviewed,
        "total_candidates": total_candidates,
        "reviewed_count": reviewed_count,
        "status": "ok",
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
