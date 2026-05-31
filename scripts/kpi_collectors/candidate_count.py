#!/usr/bin/env python3
"""KPI collector: count candidates by status.

Emits: {"pending": N, "approved": N, "rejected": N, "status": "ok"}
"""

from __future__ import annotations

import json
import re
import sys
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
    counts: dict[str, int] = {"pending": 0, "approved": 0, "rejected": 0}

    if not CANDIDATES_DIR.is_dir():
        result = {**counts, "status": "ok", "note": "candidates dir not found"}
        print(json.dumps(result))
        return 0

    for path in CANDIDATES_DIR.iterdir():
        if (
            path.suffix != ".md"
            or path.name in ("SCHEMA.md",)
            or path.name.startswith("_")
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta = _parse_frontmatter(text)
        status = meta.get("status", "pending").strip().lower()
        if status in counts:
            counts[status] += 1
        else:
            counts["pending"] += 1  # unknown status → treat as pending

    result = {**counts, "status": "ok"}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
