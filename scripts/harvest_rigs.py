#!/usr/bin/env python3
"""Cross-rig knowledge harvest — session-end promotion to repo learnings hub.

Usage:
  python scripts/harvest_rigs.py              # dry-run scan
  python scripts/harvest_rigs.py --execute    # promote + write catalog
  python scripts/harvest_rigs.py --session-end
  python scripts/harvest_rigs.py --roots ~/gt/other-rig
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from knowledge.harvest_rigs import run_harvest, run_session_harvest  # noqa: E402


def _parse_roots(raw: str | None) -> list[Path] | None:
    if not raw:
        return None
    return [Path(p.strip()) for p in raw.split(",") if p.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Harvest learnings across rig .agents/ trees"
    )
    parser.add_argument(
        "--execute", action="store_true", help="Copy promoted files (default: dry-run)"
    )
    parser.add_argument(
        "--session-end", action="store_true", help="Lite harvest for session compact"
    )
    parser.add_argument("--roots", help="Comma-separated extra rig roots to scan")
    parser.add_argument("--min-confidence", type=float, default=0.5)
    parser.add_argument(
        "--global-hub", action="store_true", help="Promote to ~/.agents/learnings/"
    )
    args = parser.parse_args(argv)

    extra = _parse_roots(args.roots)
    dry_run = not args.execute

    if args.session_end:
        report = run_session_harvest(
            REPO, dry_run=dry_run, min_confidence=max(args.min_confidence, 0.6)
        )
    else:
        report = run_harvest(
            REPO,
            extra_roots=extra,
            min_confidence=args.min_confidence,
            dry_run=dry_run,
            global_hub=args.global_hub,
        )

    print(json.dumps(report.to_dict(), indent=2))

    # KOS Stage 4 integration: after harvesting learnings, run pattern extraction.
    # This populates .agents/patterns/ from the newly promoted learnings.
    # To trigger: import and call extract_patterns.extract_patterns(dry_run=dry_run)
    # from scripts/extract_patterns.py — kept separate to avoid circular deps.
    # Example:
    #   from extract_patterns import extract_patterns
    #   extract_patterns(dry_run=dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
