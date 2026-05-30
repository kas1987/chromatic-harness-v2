#!/usr/bin/env python3
"""Mark duplicate/test closure intake entries as skipped; keep latest per id."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QUEUE = REPO / "07_LOGS_AND_AUDIT" / "intake_queue.jsonl"

# Test-mission follow-ups from harness E2E / magnet tests — not real work items.
SKIP_TITLE_PREFIXES = (
    "Run bd ready",
    "Auto-proceed with next mission phase.",
    "Halt mission and escalate to human reviewer.",
    "Proceed with reversible, bounded changes only.",
)


def main() -> int:
    if not QUEUE.is_file():
        print("No intake queue file", file=sys.stderr)
        return 1

    lines = [ln for ln in QUEUE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    seen_ids: dict[str, int] = {}
    out: list[str] = []
    skipped = 0
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    for raw in lines:
        row = json.loads(raw)
        eid = row.get("id", "")
        title = row.get("title", "")
        status = row.get("status", "")

        if status == "queued":
            if any(title.startswith(p) for p in SKIP_TITLE_PREFIXES):
                row["status"] = "skipped"
                row["error"] = "dedupe_intake_queue: test/closure noise"
                row["processed_at"] = now
                skipped += 1
            elif eid in seen_ids:
                row["status"] = "skipped"
                row["error"] = "dedupe_intake_queue: duplicate id"
                row["processed_at"] = now
                skipped += 1
            else:
                seen_ids[eid] = len(out)

        out.append(json.dumps(row, ensure_ascii=False))

    QUEUE.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(json.dumps({"skipped": skipped, "kept_lines": len(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
