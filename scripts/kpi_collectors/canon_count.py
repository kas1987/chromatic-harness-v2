#!/usr/bin/env python3
"""KPI Collector: canon_count — counts entries in canon_registry.yaml by status."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH = ROOT / "00_SOURCE_OF_TRUTH" / "canon_registry.yaml"


def collect() -> dict:
    try:
        if not REGISTRY_PATH.exists():
            return {
                "kpi": "canon_count",
                "status": "not_instrumented",
                "note": f"Registry not found: {REGISTRY_PATH}",
            }
        text = REGISTRY_PATH.read_text(encoding="utf-8")
        # Count status values from YAML entries (simple pattern match — no PyYAML dep)
        status_values = re.findall(r"^\s{4}status:\s*(\S+)", text, re.MULTILINE)
        counts: dict[str, int] = {}
        for s in status_values:
            s = s.strip('"').strip("'")
            counts[s] = counts.get(s, 0) + 1
        total = sum(counts.values())
        return {
            "kpi": "canon_count",
            "active": counts.get("active", 0),
            "deprecated": counts.get("deprecated", 0),
            "total": total,
            "by_status": counts,
            "status": "ok",
        }
    except Exception as e:
        return {"kpi": "canon_count", "status": "error", "note": str(e)}


if __name__ == "__main__":
    print(json.dumps(collect()))
