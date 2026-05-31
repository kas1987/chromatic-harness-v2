#!/usr/bin/env python3
"""KPI collector: KOS Stage 8 feedback-loop health.

Measures how much agent-generated knowledge is flowing back into the candidate
queue. A learning-sourced candidate is the signal that the flywheel compounded.

Emits:
  {
    "feedback_loop_pct": float,   # learning-sourced / total candidates * 100
    "learning_candidates": int,
    "total_candidates": int,
    "status": "ok"
  }
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CANDIDATES_DIR = REPO / ".agents" / "candidates"

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
    total = 0
    learning_sourced = 0

    if CANDIDATES_DIR.is_dir():
        for path in CANDIDATES_DIR.iterdir():
            if (
                path.suffix != ".md"
                or path.name in ("SCHEMA.md",)
                or path.name.startswith("_")
            ):
                continue
            try:
                meta = _parse_frontmatter(
                    path.read_text(encoding="utf-8", errors="replace")
                )
            except OSError:
                continue
            total += 1
            if meta.get("source_type", "").strip().lower() == "learning":
                learning_sourced += 1

    pct = round(learning_sourced / total * 100, 1) if total else 0.0
    print(
        json.dumps(
            {
                "feedback_loop_pct": pct,
                "learning_candidates": learning_sourced,
                "total_candidates": total,
                "status": "ok",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
