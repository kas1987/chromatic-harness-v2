#!/usr/bin/env python3
"""Generate a compact harvest trend snapshot from latest harvest outputs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
HARVEST_LATEST = REPO / ".agents" / "harvest" / "latest.json"
OUT_DIR = REPO / "07_LOGS_AND_AUDIT" / "harvest_trends"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Harvest Trends",
        "",
        f"- generated_at_utc: {report.get('generated_at_utc', '')}",
        f"- source: {report.get('source', '')}",
        f"- rigs_scanned: {report.get('rigs_scanned', 0)}",
        f"- artifacts_found: {report.get('artifacts_found', 0)}",
        f"- unique_count: {report.get('unique_count', 0)}",
        f"- duplicate_count: {report.get('duplicate_count', 0)}",
        f"- promoted_count: {report.get('promoted_count', 0)}",
        f"- duplicate_ratio: {report.get('duplicate_ratio', 0.0):.3f}",
        "",
        "## Rigs",
    ]
    rigs = report.get("rig_names") or []
    if rigs:
        lines.extend([f"- {name}" for name in rigs])
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize harvest trend metrics")
    parser.add_argument("--write", action="store_true", help="Write latest outputs")
    args = parser.parse_args()

    src = _load_json(HARVEST_LATEST)
    rigs = src.get("rigs_scanned") if isinstance(src.get("rigs_scanned"), list) else []
    artifacts_found = int(src.get("artifacts_found") or 0)
    unique_count = int(src.get("unique_count") or 0)
    duplicate_count = int(src.get("duplicate_count") or 0)
    promoted = src.get("promoted") if isinstance(src.get("promoted"), list) else []

    report = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": str(HARVEST_LATEST),
        "rigs_scanned": len(rigs),
        "rig_names": rigs,
        "artifacts_found": artifacts_found,
        "unique_count": unique_count,
        "duplicate_count": duplicate_count,
        "promoted_count": len(promoted),
        "duplicate_ratio": (float(duplicate_count) / float(artifacts_found)) if artifacts_found > 0 else 0.0,
    }

    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (OUT_DIR / "latest.md").write_text(_to_markdown(report), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
