#!/usr/bin/env python3
"""Count files in .agents/raw_capture/ by status.

Usage:
  python scripts/kpi_collectors/capture_count.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
RAW_CAPTURE_DIR = REPO / ".agents" / "raw_capture"


def main() -> int:
    if not RAW_CAPTURE_DIR.exists():
        result = {"raw_count": 0, "status": "ok"}
        print(json.dumps(result))
        return 0

    # Count all .md files (excluding .gitkeep)
    md_files = [f for f in RAW_CAPTURE_DIR.glob("*.md") if f.name != ".gitkeep"]
    raw_count = len(md_files)

    result = {"raw_count": raw_count, "status": "ok"}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
