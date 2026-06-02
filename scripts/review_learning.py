#!/usr/bin/env python3
"""Mine recurring reviewer patterns from review findings (PDR S Phase / AC8).

Reads the append-only findings log and emits aggregated ``reviewer_pattern`` records
(reviewer + finding_type frequency). Repeated feedback becomes a learning artifact the
orchestrator can use to pre-empt the same class of finding. The patterns file is a
derived view, regenerated each run from the source findings.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_BASE = "07_LOGS_AND_AUDIT/review_intake"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # tolerate partial writes
    return rows


def mine_patterns(findings: List[Dict[str, Any]], min_count: int) -> List[Dict[str, Any]]:
    counts: Counter = Counter()
    for f in findings:
        author = f.get("author") or "unknown"
        ftype = f.get("finding_type") or "unclear"
        repo = f.get("repo") or "unknown/repo"
        counts[(repo, author, ftype)] += 1

    patterns = []
    for (repo, author, ftype), count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
        if count < min_count:
            continue
        patterns.append(
            {
                "pattern_id": f"RP-{repo.replace('/', '-')}-{author}-{ftype}".upper(),
                "repo": repo,
                "reviewer": author,
                "finding_type": ftype,
                "occurrences": count,
                "recommendation": f"Pre-empt '{ftype}' feedback from {author}: add a gate/check before review.",
                "updated_at": utc_now(),
            }
        )
    return patterns


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--findings", default=f"{DEFAULT_BASE}/findings.jsonl")
    parser.add_argument("--patterns", default=f"{DEFAULT_BASE}/reviewer_patterns.jsonl")
    parser.add_argument("--min-count", type=int, default=2, help="Minimum occurrences to record a pattern")
    args = parser.parse_args()

    findings = read_jsonl(Path(args.findings))
    patterns = mine_patterns(findings, args.min_count)

    out = Path(args.patterns)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for p in patterns:
            f.write(json.dumps(p, sort_keys=True) + "\n")

    print(json.dumps({"findings_scanned": len(findings), "patterns_written": len(patterns)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
